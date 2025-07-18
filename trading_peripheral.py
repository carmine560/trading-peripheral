"""Manage SBI Securities data and integrate with other services."""

from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from io import StringIO
import argparse
import configparser
import inspect
import os
import re
import sys

from lxml import html
from lxml.etree import Element
import chardet
import pandas as pd
import pytz
import requests

import browser_driver
import configuration
import data_utilities
import datetime_utilities
import file_utilities
import google_services
import initializer
import process_utilities
import web_utilities


class Trade(initializer.Initializer):
    """Represent a trade process for a specific vendor."""

    def __init__(self, vendor, process):
        """Initialize the Trade with the vendor and process."""
        super().__init__(vendor, process, __file__)
        self.investment_tools_news_section = (
            f"{self.vendor} Investment Tools News"
        )
        self.release_notes_section = f"{self.process} Release Notes"
        self.maintenance_schedules_section = (
            f"{self.vendor} Maintenance Schedules"
        )
        self.order_status_section = f"{self.vendor} Order Status"
        self.instruction_items = {
            "all_keys": initializer.extract_commands(
                inspect.getsource(browser_driver.execute_action)
            ),
            "control_flow_keys": {"exist", "for"},
            "additional_value_keys": {"send_keys"},
            "no_value_keys": {"refresh"},
        }


def main():
    """Execute the main program based on command-line arguments."""
    args = get_arguments()
    trade = Trade(*args.P)

    file_utilities.create_launchers_exit(args, __file__)
    configure_exit(args, trade)

    try:
        config = configure(trade)

        if args.t:
            check_web_page_send_email_message(
                trade, config, trade.investment_tools_news_section
            )
        if args.r:
            check_web_page_send_email_message(
                trade, config, trade.release_notes_section
            )
        if args.m:
            insert_maintenance_schedules(trade, config)
        if any((args.s, args.S, args.o)):
            configuration.ensure_section_exists(config, trade.actions_section)
            driver = browser_driver.initialize(
                headless=config["General"].getboolean("headless"),
                user_data_directory=config["General"]["user_data_directory"],
                profile_directory=config["General"]["profile_directory"],
                implicitly_wait=float(config["General"]["implicitly_wait"]),
            )
            if args.s:
                browser_driver.execute_action(
                    driver,
                    config[trade.actions_section][
                        f"replace_{trade.vendor}_watchlists"
                    ],
                )
            if args.S:
                browser_driver.execute_action(
                    driver,
                    config[trade.actions_section][
                        f"replace_{trade.process}_watchlists"
                    ],
                )
            if args.o:
                browser_driver.execute_action(
                    driver, config[trade.actions_section]["get_order_status"]
                )
                if trade.vendor in BROKERAGE_ORDER_STATUS_FUNCTIONS:
                    BROKERAGE_ORDER_STATUS_FUNCTIONS[trade.vendor](
                        trade, config, driver
                    )
                else:
                    extract_unsupported_brokerage_order_status(trade.vendor)

            driver.quit()
        if args.w:
            configuration.ensure_section_exists(config, trade.process)
            file_utilities.backup_file(
                config[trade.process]["watchlists"],
                backup_directory=config[trade.process]["backup_directory"],
            )
        if args.d or args.D:
            configuration.ensure_section_exists(config, trade.process)
            if process_utilities.is_running(trade.process):
                print(f"'{trade.process}' is running.")
                sys.exit(1)

            application_data_directory = config[trade.process][
                "application_data_directory"
            ]
            snapshot_directory = config[trade.process]["snapshot_directory"]
            fingerprint = config["General"]["fingerprint"]
            if args.d:
                file_utilities.archive_encrypt_directory(
                    application_data_directory,
                    snapshot_directory,
                    fingerprint=fingerprint,
                )
            if args.D:
                snapshot = os.path.join(
                    snapshot_directory,
                    os.path.basename(application_data_directory)
                    + ".tar.xz.gpg",
                )
                output_directory = os.path.dirname(application_data_directory)
                file_utilities.decrypt_extract_file(snapshot, output_directory)
    except configuration.ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error: {e}")
        sys.exit(1)


def get_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()

    parser.add_argument(
        "-P",
        nargs=2,
        default=("SBI Securities", "HYPERSBI2"),
        help="set the brokerage and the process [defaults: %(default)s]",
        metavar=("BROKERAGE", "PROCESS|EXECUTABLE_PATH"),
    )
    parser.add_argument(
        "-t",
        action="store_true",
        help="check the 'BROKERAGE' investment tools web page"
        " and send a notification via Gmail if it is updated",
    )
    parser.add_argument(
        "-r",
        action="store_true",
        help="check the 'PROCESS' release notes"
        " and send a notification via Gmail if they are updated",
    )
    parser.add_argument(
        "-m",
        action="store_true",
        help="insert 'PROCESS' maintenance schedules into Google Calendar",
    )
    parser.add_argument(
        "-s",
        action="store_true",
        help="replace watchlists on the 'BROKERAGE' website"
        " with the 'PROCESS' watchlists",
    )
    parser.add_argument(
        "-S",
        action="store_true",
        help="replace the 'PROCESS' watchlists"
        " with watchlists on the 'BROKERAGE' website",
    )
    parser.add_argument(
        "-o",
        action="store_true",
        help="extract the order status"
        " from the 'BROKERAGE' order status web page"
        " and copy it to the clipboard",
    )
    parser.add_argument(
        "-w", action="store_true", help="backup the 'PROCESS' watchlists"
    )
    parser.add_argument(
        "-d",
        action="store_true",
        help="take a snapshot of the 'PROCESS' application data",
    )
    parser.add_argument(
        "-D",
        action="store_true",
        help="restore the 'PROCESS' application data from a snapshot",
    )

    file_utilities.add_launcher_options(group)
    group.add_argument(
        "-G", action="store_true", help="configure general options and exit"
    )
    group.add_argument(
        "-O",
        action="store_true",
        help="configure order status formats and exit",
    )
    group.add_argument(
        "-A", action="store_true", help="configure actions and exit"
    )
    group.add_argument(
        "-C", action="store_true", help="check configuration changes and exit"
    )

    return parser.parse_args(None if sys.argv[1:] else ["-h"])


def configure(trade, can_interpolate=True, can_override=True):
    """Configure the trade process based on the provided parameters."""
    if can_interpolate:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
    else:
        config = configparser.ConfigParser(interpolation=None)

    config["General"] = {
        "headless": "True",
        "user_data_directory": "",
        "profile_directory": "Default",
        "implicitly_wait": "4",
        "email_message_from": "",
        "email_message_to": "",
        "fingerprint": "",
    }

    if trade.vendor == "SBI Securities":
        config[trade.investment_tools_news_section] = {
            "url": (
                "https://site2.sbisec.co.jp/ETGate/"
                "?_ControlID=WPLETmgR001Control"
                "&_PageID=WPLETmgR001Mdtl20&_DataStoreID=DSWPLETmgR001Control"
                "&_ActionID=DefaultAID&burl=search_home&cat1=home&cat2=tool"
                "&dir=tool%2F&file=home_tool.html&getFlg=on&OutSide=on#"
            ),
            "latest_news_xpath": '//*[@id="tab1_news"]/li[1]/p/a',
            "latest_news_text": "",
        }
        ALL_SERVICE_NAME = "すべてのサービス"
        config[trade.maintenance_schedules_section] = {
            "url": (
                "https://search.sbisec.co.jp/v2/popwin/info/home"
                "/pop6040_maintenance.html"
            ),
            "timezone": "Asia/Tokyo",
            "last_inserted": "",
            "calendar_id": "",
            "all_service_xpath": (
                '//p[contains(@class, "mt-x-2")'
                f' and contains(., "{ALL_SERVICE_NAME}")]'
            ),
            "all_service_name": ALL_SERVICE_NAME,
            "services": (
                ALL_SERVICE_NAME,
                "HYPER SBI 2",
                "HYPER SBI2",
                "メインサイト",
            ),
            "service_xpath": (
                '//span[contains(@class, "font-xs font-bold")'
                ' and text()="{0}"]'
            ),
            "function_xpath": "following::p[1]",
            "datetime_xpath": "ancestor::li[1]/div[1]",
            "range_splitter_regex": "〜|～",
            "datetime_regex": (
                r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日（[^）]+）(\d{1,2}:\d{2})$$"
            ),
            "year_group": "1",
            "month_group": "2",
            "day_group": "3",
            "time_group": "4",
            "previous_bodies": {},
        }
        config[trade.order_status_section] = {
            "output_columns": (),
            "table_identifier": "注文種別",
            "exclusion": {
                "equals": ("1", ("取消完了",)),
                "startswith": (
                    "${execution_column}",
                    ("逆指値：現在値が", "逆指値執行済：現在値が"),
                ),
            },
            "execution_column": "3",
            "symbol_regex": r"^.* (\d{4}) 東証$$",
            "symbol_replacement": r"\1",
            "margin_trading": "信新",
            "buying_on_margin": "信新買",
            "execution": "約定",
            "datetime_column": "5",
            "datetime_regex": r"^(\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})$$",
            "date_replacement": r"\1",
            "time_replacement": r"\2",
            "size_column": "6",
            "price_column": "7",
        }

    if trade.process == "HYPERSBI2":
        config[trade.release_notes_section] = {
            "url": (
                "https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112_update.html"
            ),
            "latest_news_xpath": '//p[contains(@class, "Rnote__ver")]',
            "latest_news_text": "",
        }
        config[trade.process] = {
            "application_data_directory": os.path.join(
                os.path.expandvars("%APPDATA%"), trade.vendor, trade.process
            ),
            "watchlists": "",
            "backup_directory": "",
            "snapshot_directory": os.path.join(
                os.path.expanduser("~"), "Downloads"
            ),
        }
        config[trade.actions_section] = {
            f"replace_{trade.vendor}_watchlists": [
                ("get", "https://www.sbisec.co.jp/ETGate/"),
                ("sleep", "0.8"),
                ("click", '//input[@name="ACT_login"]'),
                ("click", '//a[.//text()="ポートフォリオ"]'),
                ("click", '//a[text()="登録銘柄リストの追加・置き換え"]'),
                (
                    "click",
                    '//img[@alt="登録銘柄リストの追加・置き換え機能を利用する"]',
                ),
                ("click", '//*[@name="tool_from" and @value="3"]'),
                ("click", '//input[@value="次へ"]'),
                ("click", '//*[@name="tool_to_1" and @value="1"]'),
                ("click", '//input[@value="次へ"]'),
                ("click", '//*[@name="add_replace_tool_01" and @value="1_2"]'),
                ("click", '//input[@value="確認画面へ"]'),
                ("click", '//input[@value="指示実行"]'),
            ],
            f"replace_{trade.process}_watchlists": [
                ("get", "https://www.sbisec.co.jp/ETGate/"),
                ("sleep", "0.8"),
                ("click", '//input[@name="ACT_login"]'),
                ("click", '//a[.//text()="ポートフォリオ"]'),
                ("click", '//a[text()="登録銘柄リストの追加・置き換え"]'),
                (
                    "click",
                    '//img[@alt="登録銘柄リストの追加・置き換え機能を利用する"]',
                ),
                ("click", '//*[@name="tool_from" and @value="1"]'),
                ("click", '//input[@value="次へ"]'),
                ("click", '//*[@name="tool_to_3" and @value="3"]'),
                ("click", '//input[@value="次へ"]'),
                ("click", '//*[@name="add_replace_tool_03" and @value="3_2"]'),
                ("click", '//input[@value="確認画面へ"]'),
                ("click", '//input[@value="指示実行"]'),
            ],
            "get_order_status": [
                ("get", "https://www.sbisec.co.jp/ETGate/"),
                ("sleep", "0.8"),
                ("click", '//input[@name="ACT_login"]'),
                ("click", '//a[.//text()="口座管理"]'),
                ("click", '//p/a[text()="注文照会"]'),
            ],
        }

        latest_modified_time = 0.0
        identifier = ""
        for f in os.listdir(
            config[trade.process]["application_data_directory"]
        ):
            if re.fullmatch("[0-9a-z]{32}", f):
                modified_time = os.path.getmtime(
                    os.path.join(
                        config[trade.process]["application_data_directory"], f
                    )
                )
                if modified_time > latest_modified_time:
                    latest_modified_time = modified_time
                    identifier = f
        if identifier:
            config[trade.process]["watchlists"] = os.path.join(
                config[trade.process]["application_data_directory"],
                identifier,
                "portfolio.json",
            )
        else:
            print("Unspecified identifier.")
            sys.exit(1)

    if can_override:
        config.read(trade.config_path, encoding="utf-8")

    return config


def configure_exit(args, trade):
    """Configure parameters based on command-line arguments and exit."""
    backup_parameters = {"number_of_backups": 8}
    if any((args.G, args.O, args.A)):
        config = configure(trade, can_interpolate=False)
        for argument, (section, option, prompts, items, all_values) in {
            "G": ("General", None, None, None, None),
            "O": (
                trade.order_status_section,
                "output_columns",
                {"value": "column", "end_of_list": "end of columns"},
                None,
                (
                    (
                        "None",
                        "entry_date",
                        "entry_price",
                        "entry_time",
                        "exit_date",
                        "exit_price",
                        "exit_time",
                        "size",
                        "symbol",
                        "trade_style",
                        "trade_type",
                    ),
                ),
            ),
            "A": (
                trade.actions_section,
                None,
                {
                    "key": "command",
                    "value": "argument",
                    "additional_value": "additional argument",
                    "end_of_list": "end of commands",
                },
                trade.instruction_items,
                None,
            ),
        }.items():
            if getattr(args, argument):
                configuration.modify_section(
                    config,
                    section,
                    trade.config_path,
                    backup_parameters=backup_parameters,
                    option=option,
                    prompts=prompts,
                    items=items,
                    all_values=all_values,
                )
                break

        sys.exit()
    elif args.C:
        configuration.check_config_changes(
            configure(trade, can_interpolate=False, can_override=False),
            trade.config_path,
            backup_parameters=backup_parameters,
        )
        sys.exit()


def insert_maintenance_schedules(trade, config):
    """Insert maintenance schedules into a Google Calendar."""
    configuration.ensure_section_exists(
        config, trade.maintenance_schedules_section
    )

    section = config[trade.maintenance_schedules_section]
    tzinfo = pytz.timezone(section["timezone"])
    now = datetime.now(tzinfo)

    head = web_utilities.make_head_request(section["url"])
    last_inserted = (
        datetime.fromisoformat(section["last_inserted"])
        if section["last_inserted"]
        else datetime.min.replace(tzinfo=tzinfo)
    )
    last_inserted = max(last_inserted, now - timedelta(days=29))
    if parsedate_to_datetime(head.headers["last-modified"]) <= last_inserted:
        return

    response = requests.get(section["url"], timeout=5)
    response.encoding = chardet.detect(response.content)["encoding"]
    root = html.fromstring(response.text)
    match_object = re.search("<title>(.*)</title>", response.text)
    if match_object:
        title = match_object.group(1)

    try:
        all_service_element = root.xpath(section["all_service_xpath"])[0]
        match_object = re.search(r"//(\w+)", section["service_xpath"])
        if match_object:
            pre_element = Element(match_object.group(1))
            match_object = re.search(
                r"@class, +\"(.+?)\"", section["service_xpath"]
            )
            if match_object:
                pre_element.set("class", match_object.group(1))
                pre_element.text = section["all_service_name"]
                all_service_element.addprevious(pre_element)
    except IndexError:
        pass

    resource, section["calendar_id"] = google_services.get_calendar_resource(
        os.path.join(trade.config_directory, "token.json"),
        section["calendar_id"],
        trade.maintenance_schedules_section,
        section["timezone"],
    )

    previous_bodies = configuration.evaluate_value(section["previous_bodies"])
    for service in configuration.evaluate_value(section["services"]):
        for schedule in root.xpath(section["service_xpath"].format(service)):
            function = schedule.xpath(section["function_xpath"])[0].xpath(
                "normalize-space(.)"
            )
            datetimes = (
                schedule.xpath(section["datetime_xpath"])[0]
                .text_content()
                .split("\n")
            )

            for index, _ in enumerate(datetimes):
                datetime_range = re.split(
                    re.compile(section["range_splitter_regex"]),
                    datetimes[index].strip(),
                )

                if len(datetime_range) != 2:
                    continue

                datetime_string = re.sub(
                    section["datetime_regex"],
                    lambda match_object: replace_datetime(
                        match_object, section, now, tzinfo
                    ),
                    datetime_range[0],
                )
                start = tzinfo.localize(
                    datetime.strptime(
                        datetime_utilities.normalize_datetime_string(
                            datetime_string
                        ),
                        "%Y-%m-%d %H:%M",
                    )
                )
                if re.fullmatch(r"\d{1,2}:\d{2}", datetime_range[1]):
                    datetime_string = (
                        start.strftime("%Y-%m-%d ") + datetime_range[1]
                    )
                else:
                    datetime_string = re.sub(
                        section["datetime_regex"],
                        lambda match_object: replace_datetime(
                            match_object, section, now, tzinfo
                        ),
                        datetime_range[1],
                    )

                end = tzinfo.localize(
                    datetime.strptime(
                        datetime_utilities.normalize_datetime_string(
                            datetime_string
                        ),
                        "%Y-%m-%d %H:%M",
                    )
                )

                body = {
                    "summary": f"🛠️ {service}: {function}",
                    "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": end.isoformat()},
                    "reminders": {"useDefault": False},
                    "source": {"title": title, "url": section["url"]},
                }
                body_tuple = data_utilities.dictionary_to_tuple(body)

                if body_tuple not in previous_bodies.get(service, []):
                    google_services.insert_calendar_event(
                        resource, section["calendar_id"], body
                    )

                    previous_bodies.setdefault(service, []).append(body_tuple)
                    maximum_number_of_bodies = 32
                    if (
                        len(previous_bodies[service])
                        > maximum_number_of_bodies
                    ):
                        previous_bodies[service] = previous_bodies[service][
                            -maximum_number_of_bodies:
                        ]

                    section["previous_bodies"] = str(previous_bodies)

    section["last_inserted"] = now.isoformat()
    configuration.write_config(config, trade.config_path)


def replace_datetime(match_object, section, now, tzinfo):
    """Replace matched datetime strings with formatted strings."""
    matched_year = match_object.group(int(section["year_group"]))
    matched_month = match_object.group(int(section["month_group"]))
    matched_day = match_object.group(int(section["day_group"]))
    matched_time = match_object.group(int(section["time_group"]))
    if matched_year:
        return f"{matched_year}-{matched_month}-{matched_day} {matched_time}"

    assumed_year = int(now.strftime("%Y"))
    timedelta_object = (
        tzinfo.localize(
            datetime.strptime(
                f"{assumed_year}-{matched_month}-{matched_day} {matched_time}",
                "%Y-%m-%d %H:%M",
            )
        )
        - now
    )
    threshold = timedelta(days=365 - 30)
    if timedelta_object < -threshold:
        assumed_year = assumed_year + 1
    elif timedelta_object > threshold:
        assumed_year = assumed_year - 1
    return f"{assumed_year}-{matched_month}-{matched_day} {matched_time}"


def check_web_page_send_email_message(trade, config, section):
    """Check the web page and send an email message if an update is found."""
    configuration.ensure_section_exists(config, section)

    response = requests.get(config[section]["url"], timeout=5)
    response.encoding = chardet.detect(response.content)["encoding"]
    root = html.fromstring(response.text)

    latest_news_text = (
        root.xpath(config[section]["latest_news_xpath"])[0]
        .text_content()
        .strip()
    )
    if latest_news_text == config[section]["latest_news_text"]:
        return

    print(latest_news_text)

    google_services.send_email_message(
        os.path.join(trade.config_directory, "token.json"),
        section,
        config["General"]["email_message_from"],
        config["General"]["email_message_to"],
        f"{latest_news_text}\n{config[section]['url']}",
    )

    config[section]["latest_news_text"] = latest_news_text
    configuration.write_config(config, trade.config_path)


def extract_sbi_securities_order_status(trade, config, driver):
    """Extract order status from a webpage and copy it to the clipboard."""
    section = config[trade.order_status_section]

    try:
        dfs = pd.read_html(
            StringIO(driver.page_source),
            match=section["table_identifier"],
            flavor="lxml",
        )
    except ValueError as e:
        print(e)
        sys.exit(1)

    exclusion = configuration.evaluate_value(section["exclusion"])
    execution_column = int(section["execution_column"])  # TODO: Rename.
    datetime_column = int(section["datetime_column"])
    size_column = int(section["size_column"])
    price_column = int(section["price_column"])
    output_columns = configuration.evaluate_value(section["output_columns"])

    index = 0  # TODO: Make configurable.
    df = dfs[1][  # TODO: Make configurable.
        ~dfs[1]
        .iloc[:, int(exclusion["equals"][0])]
        .isin(exclusion["equals"][1])
        & ~dfs[1]
        .iloc[:, int(exclusion["startswith"][0])]
        .str.startswith(exclusion["startswith"][1])
    ]
    size_price = pd.DataFrame(columns=("size", "price"))
    results = pd.DataFrame(columns=output_columns)

    while index < len(df):
        if df.iloc[index, execution_column] == section["execution"]:
            if len(size_price) == 0:
                size_price.loc[0] = [
                    df.iloc[index - 1, size_column],
                    df.iloc[index - 1, price_column],
                ]

            size_price.loc[len(size_price)] = [
                df.iloc[index, size_column],
                df.iloc[index, price_column],
            ]
            if (
                index + 1 == len(df)
                or df.iloc[index + 1, execution_column] != section["execution"]
            ):
                size_price_index = 0
                size_price = size_price.astype(float)
                summation = 0
                while size_price_index < len(size_price):
                    summation += (
                        size_price.loc[size_price_index, "size"]
                        * size_price.loc[size_price_index, "price"]
                    )
                    size_price_index += 1

                average_price = summation / size_price["size"].sum()
                if (
                    section["margin_trading"]
                    in df.iloc[index - len(size_price), execution_column]
                ):
                    entry_price = average_price
                else:
                    results.loc[len(results) - 1, "exit_price"] = average_price

                size_price = pd.DataFrame(columns=("size", "price"))

            index += 1
        else:
            symbol = re.sub(
                section["symbol_regex"],
                section["symbol_replacement"],
                df.iloc[index, execution_column],
            )
            size = df.iloc[index + 1, size_column]
            trade_style = "day"  # TODO: Make configurable.
            if (
                section["margin_trading"]
                in df.iloc[index + 1, execution_column]
            ):
                entry_date = re.sub(
                    section["datetime_regex"],
                    section["date_replacement"],
                    df.iloc[index + 2, datetime_column],
                )
                entry_time = re.sub(
                    section["datetime_regex"],
                    section["time_replacement"],
                    df.iloc[index + 2, datetime_column],
                )
                trade_type = (
                    "long"
                    if section["buying_on_margin"]
                    in df.iloc[index + 1, execution_column]
                    else "short"
                )

                entry_price = df.iloc[index + 2, price_column]
            else:
                exit_date = re.sub(
                    section["datetime_regex"],
                    section["date_replacement"],
                    df.iloc[index + 2, datetime_column],
                )
                exit_time = re.sub(
                    section["datetime_regex"],
                    section["time_replacement"],
                    df.iloc[index + 2, datetime_column],
                )
                exit_price = df.iloc[index + 2, price_column]

                results.loc[len(results)] = [
                    {
                        "entry_date": entry_date,
                        "entry_time": entry_time,
                        "symbol": symbol,
                        "size": size,
                        "trade_type": trade_type,
                        "trade_style": trade_style,
                        "entry_price": entry_price,
                        "exit_date": exit_date,
                        "exit_time": exit_time,
                        "exit_price": exit_price,
                    }.get(column)
                    for column in output_columns
                ]

            index += 3

    if len(results) == 1:
        results = results.reindex([0, 1])

    results.to_clipboard(index=False, header=False)


def extract_unsupported_brokerage_order_status(brokerage):
    """Handle order status requests for unsupported brokerages."""
    print(f"Order status extraction for '{brokerage}' is not implemented.")
    return None


BROKERAGE_ORDER_STATUS_FUNCTIONS = {
    "SBI Securities": extract_sbi_securities_order_status
}

if __name__ == "__main__":
    main()

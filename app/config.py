"""Configuration defaults and interactive config flows."""

import configparser
import os
import re
import sys

from core_utilities import configuration, errors


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
        _configure_sbi_sections(config, trade)

    if trade.process == "HYPERSBI2":
        _configure_hypersbi2_sections(config, trade)

    if can_override:
        configuration.read_config(config, trade.config_path, is_encrypted=True)

    return config


def _configure_sbi_sections(config, trade):
    """Populate sections specific to SBI Securities."""
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
    all_service_name = "すべてのサービス"
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
            f' and contains(., "{all_service_name}")]'
        ),
        "all_service_name": all_service_name,
        "services": (
            all_service_name,
            "HYPER SBI 2",
            "HYPER SBI2",
            "メインサイト",
        ),
        "service_xpath": (
            '//span[contains(@class, "font-xs font-bold")' ' and text()="{0}"]'
        ),
        "function_xpath": "following::p[1]",
        "datetime_xpath": "ancestor::li[1]/div[1]",
        "range_splitter_regex": "〜|～",
        "datetime_regex": (
            r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日" r"（[^）]+）(\d{1,2}:\d{2})$$"
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
            "equals": ("${order_status_column}", ("取消完了",)),
            "startswith": (
                "${condition_column}",
                (
                    "逆指値：現在値が",
                    "逆指値執行済：現在値が",
                ),
            ),
        },
        "order_status_column": "1",
        "order_trigger_column": "2",
        "stop_order": "逆指値注文",
        "symbol_column": "3",
        "symbol_regex": r"^.* (\d{4}) 東証$$",
        "symbol_replacement": r"\1",
        "margin_transaction_type_column": "${symbol_column}",
        "margin_entry_prefix": "信新",
        "margin_long_entry": "信新買",
        "order_type_column": "7",
        "market_order": "成行",
        "condition_column": "${symbol_column}",
        "execution_column": "${symbol_column}",
        "execution": "約定",
        "datetime_column": "5",
        "datetime_regex": r"^(\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})$$",
        "date_replacement": r"\1",
        "time_replacement": r"\2",
        "size_column": "6",
        "price_column": "${order_type_column}",
    }
    config[trade.brokerage_variables_section] = {
        "username": "",
        "password": "",
    }


def _configure_hypersbi2_sections(config, trade):
    """Populate sections specific to the HYPERSBI2 process."""
    config[trade.release_notes_section] = {
        "url": "https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112_update.html",
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
        f"replace_{trade.vendor}_watchlists": _build_watchlist_actions(
            trade, "3", "1", "01", "1_2"
        ),
        f"replace_{trade.process}_watchlists": _build_watchlist_actions(
            trade, "1", "3", "03", "3_2"
        ),
        "get_order_status": [
            ("get", "https://login.sbisec.co.jp/login/entry"),
            ("sleep", "0.8"),
            (
                "send_keys",
                '//input[@name="username"]',
                f"${{{trade.brokerage_variables_section}:username}}",
            ),
            (
                "send_keys",
                '//input[@name="password"]',
                f"${{{trade.brokerage_variables_section}:password}}",
            ),
            ("click", '//button[@id="pw-btn"]'),
            (
                "exist",
                '//*[contains(@class, "_karte-close")]',
                [("click", '//*[contains(@class, "_karte-close")]')],
            ),
            ("click", '//a[.//text()="口座管理"]'),
            ("click", '//p/a[text()="注文照会"]'),
        ],
    }
    _configure_hypersbi2_watchlists(config, trade)


def _build_watchlist_actions(trade, tool_from, tool_to, name, action_id):
    """Build the repeated Selenium action list for watchlist sync."""
    return [
        ("get", "https://login.sbisec.co.jp/login/entry"),
        ("sleep", "0.8"),
        (
            "send_keys",
            '//input[@name="username"]',
            f"${{{trade.brokerage_variables_section}:username}}",
        ),
        (
            "send_keys",
            '//input[@name="password"]',
            f"${{{trade.brokerage_variables_section}:password}}",
        ),
        ("click", '//button[@id="pw-btn"]'),
        (
            "exist",
            '//*[contains(@class, "_karte-close")]',
            [("click", '//*[contains(@class, "_karte-close")]')],
        ),
        ("click", '//a[.//text()="ポートフォリオ"]'),
        (
            "click",
            '//a[text()="登録銘柄リストの追加・置き換え"]',
        ),
        (
            "click",
            (
                "//img"
                '[@alt="登録銘柄リストの追加・'
                '置き換え機能を利用する"]'
            ),
        ),
        ("click", f'//*[@name="tool_from" and @value="{tool_from}"]'),
        ("click", '//input[@value="次へ"]'),
        ("click", f'//*[@name="tool_to_{tool_to}" and @value="{tool_to}"]'),
        ("click", '//input[@value="次へ"]'),
        (
            "click",
            (
                f'//*[@name="add_replace_tool_{name}"'
                f' and @value="{action_id}"]'
            ),
        ),
        ("click", '//input[@value="確認画面へ"]'),
        ("click", '//input[@value="指示実行"]'),
    ]


def _configure_hypersbi2_watchlists(config, trade):
    """Resolve the latest watchlist identifier from application data."""
    latest_modified_time = 0.0
    identifier = ""
    application_data_directory = config[trade.process][
        "application_data_directory"
    ]
    if not os.path.isdir(application_data_directory):
        raise errors.ConfigBuildError(
            "Application data directory does not exist: "
            f"{application_data_directory}"
        )

    for entry in os.listdir(application_data_directory):
        if re.fullmatch("[0-9a-z]{32}", entry):
            modified_time = os.path.getmtime(
                os.path.join(application_data_directory, entry)
            )
            if modified_time > latest_modified_time:
                latest_modified_time = modified_time
                identifier = entry
    if identifier:
        config[trade.process]["watchlists"] = os.path.join(
            application_data_directory,
            identifier,
            "portfolio.json",
        )
        return

    print("Unspecified identifier.")
    sys.exit(1)


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
                        "entry_time",
                        "symbol",
                        "size",
                        "order_specification",
                        "entry_price",
                        "exit_time",
                        "exit_price",
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
                    is_encrypted=True,
                )
                break

        sys.exit()
    if args.C:
        configuration.check_config_changes(
            configure(trade, can_interpolate=False, can_override=False),
            trade.config_path,
            excluded_sections=(trade.brokerage_variables_section,),
            backup_parameters=backup_parameters,
            is_encrypted=True,
        )
        sys.exit()

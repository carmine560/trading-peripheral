"""Manages SBI Securities data and integrates with other services."""

from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from io import StringIO
import argparse
import base64
import configparser
import inspect
import json
import os
import re
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from lxml import html
from lxml.etree import Element
import chardet
import pandas as pd
import pytz
import requests

import browser_driver
import configuration
import file_utilities
import initializer
import process_utilities


class Trade(initializer.Initializer):
    """Represent a trade process for a specific vendor."""

    def __init__(self, vendor, process):
        """Initialize the Trade with the vendor and process."""
        super().__init__(vendor, process, __file__)
        self.maintenance_schedules_section = (
            f'{self.vendor} Maintenance Schedules')
        self.daily_sales_order_quota_section = (
            f'{self.vendor} Daily Sales Order Quota')
        self.order_status_section = f'{self.vendor} Order Status'
        self.instruction_items = {
            'all_keys': initializer.extract_commands(
                inspect.getsource(browser_driver.execute_action)),
            'control_flow_keys': {'exist', 'for'},
            'additional_value_keys': {'send_keys'},
            'no_value_keys': {'refresh'}}


def main():
    """Execute the main program based on command-line arguments."""
    args = get_arguments()
    trade = Trade(*args.P)
    backup_parameters = {'number_of_backups': 8}

    if any((args.G, args.O, args.A)):
        config = configure(trade, can_interpolate=False)
        if args.G and configuration.modify_section(
                config, 'General', trade.config_path,
                backup_parameters=backup_parameters):
            return
        if args.O and configuration.modify_option(
                config, trade.order_status_section, 'output_columns',
                trade.config_path, backup_parameters=backup_parameters,
                prompts={'value': 'column', 'end_of_list': 'end of columns'},
                all_values=(('None', 'entry_date', 'entry_price', 'entry_time',
                             'exit_date', 'exit_price', 'exit_time', 'size',
                             'symbol', 'trade_style', 'trade_type'),)):
            return
        if args.A and configuration.modify_section(
                config, trade.actions_section, trade.config_path,
                backup_parameters=backup_parameters,
                prompts={'key': 'command', 'value': 'argument',
                         'additional_value': 'additional argument',
                         'end_of_list': 'end of commands'},
                items=trade.instruction_items):
            return

        sys.exit(1)
    elif args.C:
        default_config = configure(trade, can_interpolate=False,
                                   can_override=False)
        configuration.check_config_changes(
            default_config, trade.config_path,
            excluded_sections=(trade.variables_section,),
            backup_parameters=backup_parameters)
        return
    else:
        config = configure(trade)

    if args.m:
        insert_maintenance_schedules(trade, config)
    if any((args.s, args.q, args.o)):
        driver = browser_driver.initialize(
            headless=config['General'].getboolean('headless'),
            user_data_directory=config['General']['user_data_directory'],
            profile_directory=config['General']['profile_directory'],
            implicitly_wait=float(config['General']['implicitly_wait']))
        if args.s:
            browser_driver.execute_action(
                driver,
                config[trade.actions_section]['replace_sbi_securities'])
        if args.q:
            check_daily_sales_order_quota(trade, config, driver)
        if args.o:
            browser_driver.execute_action(
                driver, config[trade.actions_section]['get_order_status'])
            extract_order_status(trade, config, driver)

        driver.quit()
    if args.w:
        file_utilities.backup_file(
            config[trade.process]['watchlists'],
            backup_directory=config[trade.process]['backup_directory'])
    if args.d or args.D:
        if process_utilities.is_running(trade.process):
            print(trade.process, 'is running.')
            sys.exit(1)
        else:
            application_data_directory = config[trade.process][
                'application_data_directory']
            snapshot_directory = config[trade.process]['snapshot_directory']
            fingerprint = config['General']['fingerprint']
            if args.d:
                file_utilities.archive_encrypt_directory(
                    application_data_directory, snapshot_directory,
                    fingerprint=fingerprint)
            if args.D:
                snapshot = os.path.join(
                    snapshot_directory,
                    os.path.basename(application_data_directory)
                    + '.tar.xz.gpg')
                output_directory = os.path.dirname(application_data_directory)
                file_utilities.decrypt_extract_file(snapshot, output_directory)


def get_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()

    parser.add_argument(
        '-P', nargs=2, default=('SBI Securities', 'HYPERSBI2'),
        help='set the brokerage and the process [defaults: %(default)s]',
        metavar=('BROKERAGE', 'PROCESS|PATH_TO_EXECUTABLE'))
    parser.add_argument(
        '-m', action='store_true',
        help='insert Hyper SBI 2 maintenance schedules into Google Calendar')
    parser.add_argument(
        '-s', action='store_true',
        help='replace watchlists on the SBI Securities website'
        ' with the Hyper SBI 2 watchlists')
    parser.add_argument(
        '-q', action='store_true',
        help='check the daily sales order quota for general margin trading'
        ' for the specified Hyper SBI 2 watchlist'
        ' and send a notification via Gmail if it is insufficient')
    parser.add_argument(
        '-o', action='store_true',
        help='extract the order status'
        ' from the SBI Securities order status web page'
        ' and copy it to the clipboard')
    parser.add_argument(
        '-w', action='store_true',
        help='backup the Hyper SBI 2 watchlists')
    parser.add_argument(
        '-d', action='store_true',
        help='take a snapshot of the Hyper SBI 2 application data')
    parser.add_argument(
        '-D', action='store_true',
        help='restore the Hyper SBI 2 application data from a snapshot')
    group.add_argument(
        '-G', action='store_true',
        help='configure general options and exit')
    group.add_argument(
        '-O', action='store_true',
        help='configure order status formats and exit')
    group.add_argument(
        '-A', action='store_true',
        help='configure actions and exit')
    group.add_argument(
        '-C', action='store_true',
        help='check configuration changes and exit')

    return parser.parse_args(None if sys.argv[1:] else ['-h'])


def configure(trade, can_interpolate=True, can_override=True):
    """Configure the trade process based on the provided parameters."""
    if can_interpolate:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
    else:
        config = configparser.ConfigParser(interpolation=None)

    config['General'] = {
        'headless': 'True',
        'user_data_directory':
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
        'profile_directory': 'Default',
        'implicitly_wait': '4',
        'email_message_from': '',
        'email_message_to': '',
        'fingerprint': ''}
    all_service_name = 'すべてのサービス'
    config[trade.maintenance_schedules_section] = {
        'url':
        ('https://search.sbisec.co.jp/v2/popwin/info/home'
         '/pop6040_maintenance.html'),
        'timezone': 'Asia/Tokyo',
        'last_inserted': '',
        'calendar_id': '',
        'all_service_xpath':
        ('//p[contains(@class, "mt-x-2") and contains(., "メインサイト")'
         f' and contains(., "{all_service_name}")]'),
        'all_service_name': all_service_name,
        'services': (all_service_name, 'HYPER SBI 2', 'HYPER SBI2',
                     'メインサイト'),
        'service_xpath':
        '//span[contains(@class, "font-xs font-bold") and text()="{0}"]',
        'function_xpath': 'following::p[1]',
        'datetime_xpath': 'ancestor::li[1]/div[1]',
        'range_splitter_regex': '〜|～',
        'datetime_regex':
        r'^(\d{4}年)?(\d{1,2})月(\d{1,2})日（[^）]+）(\d{1,2}:\d{2})$$',
        'year_group': '1',
        'month_group': '2',
        'day_group': '3',
        'time_group': '4',
        'previous_bodies': {}}
    config[trade.daily_sales_order_quota_section] = {
        'quota_watchlist': '',
        'sufficient': '◎（余裕あり）'}
    config[trade.order_status_section] = {
        'output_columns': (),
        'table_identifier': '注文種別',
        'symbol_regex': r'^.* (\d{4}) 東証$$',
        'symbol_replacement': r'\1',
        'margin_trading': '信新',
        'buying_on_margin': '信新買',
        'execution_column': '3',
        'execution': '約定',
        'datetime_column': '5',
        'datetime_regex': r'^(\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})$$',
        'date_replacement': r'\1',
        'time_replacement': r'\2',
        'size_column': '6',
        'price_column': '7'}
    config[trade.process] = {
        'application_data_directory':
        os.path.join(os.path.expandvars('%APPDATA%'), trade.vendor,
                     trade.process),
        'watchlists': '',
        'backup_directory': '',
        'snapshot_directory':
        os.path.join(os.path.expanduser('~'), 'Downloads')}
    config[trade.actions_section] = {
        'replace_sbi_securities':
        [('get', 'https://www.sbisec.co.jp/ETGate'),
         ('sleep', '0.8'),
         ('click', '//input[@name="ACT_login"]'),
         ('click', '//a[text()="ポートフォリオ"]'),
         ('click', '//a[text()="登録銘柄リストの追加・置き換え"]'),
         ('click',
          '//img[@alt="登録銘柄リストの追加・置き換え機能を利用する"]'),
         ('click', '//*[@name="tool_from" and @value="3"]'),
         ('click', '//input[@value="次へ"]'),
         ('click', '//*[@name="tool_to_1" and @value="1"]'),
         ('click', '//input[@value="次へ"]'),
         ('click', '//*[@name="add_replace_tool_01" and @value="1_2"]'),
         ('click', '//input[@value="確認画面へ"]'),
         ('click', '//input[@value="指示実行"]')],
        'get_daily_sales_order_quota':
        [('get', 'https://www.sbisec.co.jp/ETGate'),
         ('sleep', '0.8'),
         ('click', '//input[@name="ACT_login"]'),
         ('for', f'${{{trade.variables_section}:securities_codes}}',
          [('send_keys', '//*[@id="top_stock_sec"]', 'element'),
           ('send_keys', '//*[@id="top_stock_sec"]', 'enter'),
           ('click', '//a[text()="信用売"]'),
           ('exist', '//td[contains(text(), "一般/日計り売建受注枠")]',
            [('text',
              '//td[contains(text(), "一般/日計り売建受注枠")]')])])],
        'get_order_status':
        [('get', 'https://www.sbisec.co.jp/ETGate'),
         ('sleep', '0.8'),
         ('click', '//input[@name="ACT_login"]'),
         ('click', '//a[text()="注文照会"]')]}
    config[trade.variables_section] = {
        'securities_codes': ''}

    if can_override:
        config.read(trade.config_path, encoding='utf-8')

    if trade.process == 'HYPERSBI2':
        section = config[trade.process]
        if not section.get('watchlists'):
            application_data_directory = section['application_data_directory']
            latest_modified_time = 0.0
            identifier = ''
            for f in os.listdir(application_data_directory):
                if re.fullmatch('[0-9a-z]{32}', f):
                    modified_time = os.path.getmtime(os.path.join(
                        application_data_directory, f))
                    if modified_time > latest_modified_time:
                        latest_modified_time = modified_time
                        identifier = f
            if identifier:
                section['watchlists'] = os.path.join(
                    application_data_directory, identifier, 'portfolio.json')
            else:
                print('Unspecified identifier.')
                sys.exit(1)

    return config


def insert_maintenance_schedules(trade, config):
    """Insert maintenance schedules into a Google Calendar."""
    def replace_datetime(match_object):
        """Replace matched datetime strings with formatted strings."""
        matched_year = match_object.group(int(section['year_group']))
        matched_month = match_object.group(int(section['month_group']))
        matched_day = match_object.group(int(section['day_group']))
        matched_time = match_object.group(int(section['time_group']))
        if matched_year:
            return (f'{matched_year}-{matched_month}-{matched_day} '
                    f'{matched_time}')

        assumed_year = int(now.strftime('%Y'))
        timedelta_object = tzinfo.localize(datetime.strptime(
            f'{assumed_year}-{matched_month}-{matched_day} {matched_time}',
            '%Y-%m-%d %H:%M')) - now
        threshold = timedelta(days=365 - 30)
        if timedelta_object < -threshold:
            assumed_year = assumed_year + 1
        elif timedelta_object > threshold:
            assumed_year = assumed_year - 1
        return f'{assumed_year}-{matched_month}-{matched_day} {matched_time}'

    def dictionary_to_tuple(dictionary):
        """Convert a dictionary to a tuple of key-value pairs."""
        if isinstance(dictionary, dict):
            items = []
            for key, value in sorted(dictionary.items()):
                items.append((key, dictionary_to_tuple(value)))
            return tuple(items)
        return dictionary

    section = config[trade.maintenance_schedules_section]
    tzinfo = pytz.timezone(section['timezone'])
    now = datetime.now(tzinfo)

    head = requests.head(section['url'], timeout=5)
    try:
        head.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(e)
        sys.exit(1)

    last_inserted = (datetime.fromisoformat(section['last_inserted'])
                     if section['last_inserted']
                     else datetime.min.replace(tzinfo=tzinfo))
    last_inserted = max(last_inserted, now - timedelta(days=29))
    if parsedate_to_datetime(head.headers['last-modified']) <= last_inserted:
        return

    response = requests.get(section['url'], timeout=5)
    response.encoding = chardet.detect(response.content)['encoding']
    root = html.fromstring(response.text)
    match_object = re.search('<title>(.*)</title>', response.text)
    if match_object:
        title = match_object.group(1)

    resource = build('calendar', 'v3', credentials=get_credentials(
        os.path.join(trade.config_directory, 'token.json')))

    if not section['calendar_id']:
        body = {'summary': trade.maintenance_schedules_section,
                'timeZone': section['timezone']}
        try:
            calendar = resource.calendars().insert(body=body).execute()
            section['calendar_id'] = calendar['id']
        except HttpError as e:
            print(e)
            sys.exit(1)

    try:
        all_service_element = root.xpath(section['all_service_xpath'])[0]
        match_object = re.search(r'//(\w+)', section['service_xpath'])
        if match_object:
            pre_element = Element(match_object.group(1))
            match_object = re.search(r'@class, +\"(.+?)\"',
                                     section['service_xpath'])
            if match_object:
                pre_element.set('class', match_object.group(1))
                pre_element.text = section['all_service_name']
                all_service_element.addprevious(pre_element)
    except IndexError:
        pass

    previous_bodies = configuration.evaluate_value(section['previous_bodies'])
    for service in configuration.evaluate_value(section['services']):
        for schedule in root.xpath(section['service_xpath'].format(service)):
            function = schedule.xpath(
                section['function_xpath'])[0].xpath('normalize-space(.)')
            datetimes = schedule.xpath(
                section['datetime_xpath'])[0].text_content().split('\n')

            for index, _ in enumerate(datetimes):
                datetime_range = re.split(
                    re.compile(section['range_splitter_regex']),
                    datetimes[index].strip())

                if len(datetime_range) != 2:
                    continue

                datetime_string = re.sub(section['datetime_regex'],
                                         replace_datetime,
                                         datetime_range[0])
                start = tzinfo.localize(
                    datetime.strptime(datetime_string, '%Y-%m-%d %H:%M'))
                if re.fullmatch(r'\d{1,2}:\d{2}', datetime_range[1]):
                    datetime_string = (start.strftime('%Y-%m-%d ')
                                       + datetime_range[1])
                else:
                    datetime_string = re.sub(section['datetime_regex'],
                                             replace_datetime,
                                             datetime_range[1])

                end = tzinfo.localize(
                    datetime.strptime(datetime_string, '%Y-%m-%d %H:%M'))

                body = {'summary': f'🛠️ {service}: {function}',
                        'start': {'dateTime': start.isoformat()},
                        'end': {'dateTime': end.isoformat()},
                        'source': {'title': title, 'url': section['url']}}
                body_tuple = dictionary_to_tuple(body)

                if body_tuple not in previous_bodies.get(service, []):
                    try:
                        event = resource.events().insert(
                            calendarId=section['calendar_id'],
                            body=body).execute()
                        print(event.get('start')['dateTime'],
                              event.get('summary'))
                    except HttpError as e:
                        print(e)
                        sys.exit(1)

                    previous_bodies.setdefault(service, []).append(body_tuple)
                    maximum_number_of_bodies = 32
                    if (len(previous_bodies[service])
                        > maximum_number_of_bodies):
                        previous_bodies[service] = previous_bodies[
                            service][-maximum_number_of_bodies:]

                    section['previous_bodies'] = str(previous_bodies)

    section['last_inserted'] = now.isoformat()
    configuration.write_config(config, trade.config_path)


def check_daily_sales_order_quota(trade, config, driver):
    """Check the daily sales order quota and sends an email if necessary."""
    with open(config[trade.process]['watchlists'], encoding='utf-8') as f:
        watchlists = json.load(f)

    quota_watchlist = next(
        (watchlist for watchlist in watchlists['list']
         if watchlist['listName']
         == config[trade.daily_sales_order_quota_section]['quota_watchlist']),
        None)
    if quota_watchlist is None:
        print('No matching watchlist was found.')
        sys.exit(1)

    securities_codes = [item['secCd'] for item in quota_watchlist['secList']]
    config[trade.variables_section]['securities_codes'] = (
        ', '.join(securities_codes))

    text = []
    browser_driver.execute_action(
        driver, config[trade.actions_section]['get_daily_sales_order_quota'],
        text=text)

    status = ''
    for index, _ in enumerate(text):
        if (not config[trade.daily_sales_order_quota_section]['sufficient']
            in text[index]):
            status += f'{securities_codes[index]}: {text[index]}\n'

    print(status)

    if (config['General']['email_message_from']
        and config['General']['email_message_to'] and status):
        resource = build('gmail', 'v1', credentials=get_credentials(
            os.path.join(trade.config_directory, 'token.json')))

        email_message = EmailMessage()
        email_message['Subject'] = trade.daily_sales_order_quota_section
        email_message['From'] = config['General']['email_message_from']
        email_message['To'] = config['General']['email_message_to']
        email_message.set_content(status)

        body = {'raw': base64.urlsafe_b64encode(
            email_message.as_bytes()).decode()}
        try:
            resource.users().messages().send(userId='me', body=body).execute()
        except HttpError as e:
            print(e)
            sys.exit(1)


def extract_order_status(trade, config, driver):
    """Extract order status from a webpage and copies it to the clipboard."""
    # TODO: make configurable
    section = config[trade.order_status_section]

    try:
        dfs = pd.read_html(StringIO(driver.page_source),
                           match=section['table_identifier'], flavor='lxml')
    except ValueError as e:
        print(e)
        sys.exit(1)

    index = 0
    df = dfs[1]
    size_price = pd.DataFrame(columns=('size', 'price'))
    size_column = int(section['size_column'])
    price_column = int(section['price_column'])
    execution_column = int(section['execution_column'])
    datetime_column = int(section['datetime_column'])
    output_columns = configuration.evaluate_value(section['output_columns'])
    results = pd.DataFrame(columns=output_columns)
    while index < len(df):
        if df.iloc[index, execution_column] == section['execution']:
            if len(size_price) == 0:
                size_price.loc[0] = [df.iloc[index - 1, size_column],
                                     df.iloc[index - 1, price_column]]

            size_price.loc[len(size_price)] = [df.iloc[index, size_column],
                                               df.iloc[index, price_column]]
            if (index + 1 == len(df) or df.iloc[index + 1, execution_column]
                != section['execution']):
                size_price_index = 0
                size_price = size_price.astype(float)
                summation = 0
                while size_price_index < len(size_price):
                    summation += (size_price.loc[size_price_index, 'size']
                                  * size_price.loc[size_price_index, 'price'])
                    size_price_index += 1

                average_price = summation / size_price['size'].sum()
                if (section['margin_trading']
                    in df.iloc[index - len(size_price), execution_column]):
                    entry_price = average_price
                else:
                    results.loc[len(results) - 1, 'exit_price'] = average_price

                size_price = pd.DataFrame(columns=('size', 'price'))

            index += 1
        else:
            symbol = re.sub(section['symbol_regex'],
                            section['symbol_replacement'],
                            df.iloc[index, execution_column])
            size = df.iloc[index + 1, size_column]
            # TODO: make configurable
            trade_style = 'day'
            if (section['margin_trading']
                in df.iloc[index + 1, execution_column]):
                entry_date = re.sub(section['datetime_regex'],
                                    section['date_replacement'],
                                    df.iloc[index + 2, datetime_column])
                entry_time = re.sub(section['datetime_regex'],
                                    section['time_replacement'],
                                    df.iloc[index + 2, datetime_column])
                if (section['buying_on_margin']
                    in df.iloc[index + 1, execution_column]):
                    trade_type = 'long'
                else:
                    trade_type = 'short'

                entry_price = df.iloc[index + 2, price_column]
            else:
                exit_date = re.sub(section['datetime_regex'],
                                   section['date_replacement'],
                                   df.iloc[index + 2, datetime_column])
                exit_time = re.sub(section['datetime_regex'],
                                   section['time_replacement'],
                                   df.iloc[index + 2, datetime_column])
                exit_price = df.iloc[index + 2, price_column]

                results.loc[len(results)] = [
                    {'entry_date': entry_date,
                     'entry_time': entry_time,
                     'symbol': symbol,
                     'size': size,
                     'trade_type': trade_type,
                     'trade_style': trade_style,
                     'entry_price': entry_price,
                     'exit_date': exit_date,
                     'exit_time': exit_time,
                     'exit_price': exit_price}.get(column)
                    for column in output_columns]

            index += 3

    if len(results) == 1:
        results = results.reindex([0, 1])

    results.to_clipboard(index=False, header=False)


def get_credentials(token_json):
    """Obtain valid Google API credentials from a JSON token file."""
    scopes = ['https://www.googleapis.com/auth/calendar',
              'https://www.googleapis.com/auth/gmail.send']
    credentials = None
    if os.path.exists(token_json):
        credentials = Credentials.from_authorized_user_file(token_json, scopes)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    input('Path to client_secrets.json: '), scopes)
                credentials = flow.run_local_server(port=0)
            except (FileNotFoundError, ValueError) as e:
                print(e)
                sys.exit(1)
        with open(token_json, 'w', encoding='utf-8') as token:
            token.write(credentials.to_json())
    return credentials


if __name__ == '__main__':
    main()

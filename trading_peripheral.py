from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from io import StringIO
import argparse
import ast
import base64
import configparser
import csv
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
    def __init__(self, brokerage, process):
        super().__init__(brokerage, process, __file__)
        self.brokerage = self.vendor

        self.maintenance_schedules_title = (
            f'{self.brokerage} Maintenance Schedules')
        self.daily_sales_order_quota_title = (
            f'{self.brokerage} Daily Sales Order Quota')
        self.order_status_title = f'{self.brokerage} Order Status'
        self.actions_title = f'{self.process} Actions'
        self.categorized_keys = {
            'all_keys': file_utilities.extract_commands(
                inspect.getsource(browser_driver.execute_action)),
            'control_flow_keys': ('exist', 'for'),
            'additional_value_keys': ('send_keys',),
            'no_value_keys': ('refresh',)}

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-P', default=('SBI Securities', 'HYPERSBI2'),
        metavar=('BROKERAGE', 'PROCESS|PATH_TO_EXECUTABLE'), nargs=2,
        help='set the brokerage and the process [defaults: %(default)s]')
    parser.add_argument(
        '-m', action='store_true',
        help='insert Hyper SBI 2 maintenance schedules into Google Calendar')
    parser.add_argument(
        '-s', action='store_true',
        help='replace watchlists on the SBI Securities website '
        'with the Hyper SBI 2 watchlists')
    parser.add_argument(
        '-y', action='store_true',
        help='export the Hyper SBI 2 watchlists to My Portfolio '
        'on Yahoo Finance')
    parser.add_argument(
        '-q', action='store_true',
        help='check the daily sales order quota in general margin trading '
        'for the specified Hyper SBI 2 watchlist '
        'and send a notification via Gmail if insufficient')
    parser.add_argument(
        '-o', action='store_true',
        help='extract the order status from the SBI Securities web page '
        'and copy it to the clipboard')
    parser.add_argument(
        '-w', action='store_true',
        help='backup the Hyper SBI 2 watchlists')
    parser.add_argument(
        '-d', action='store_true',
        help='take a snapshot of the Hyper SBI 2 application data')
    parser.add_argument(
        '-D', action='store_true',
        help='restore the Hyper SBI 2 application data from a snapshot')
    parser.add_argument(
        '-W', action='store_true',
        help='remove the Watchlists window from the current set of windows '
        'in Hyper SBI 2 to reduce load')
    group.add_argument(
        '-G', action='store_true',
        help='configure general options and exit')
    group.add_argument(
        '-O', action='store_true',
        help='configure order status formats and exit')
    group.add_argument(
        '-C', action='store_true',
        help='check configuration changes and exit')
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    trade = Trade(*args.P)
    backup_file = {'backup_function': file_utilities.backup_file,
                   'backup_parameters': {'number_of_backups': 8}}

    if args.G or args.O:
        config = configure(trade, can_interpolate=False)
        if args.G and configuration.modify_section(
                config, 'General', trade.config_path, **backup_file):
            return
        if args.O and configuration.modify_section(
                config, trade.order_status_title, trade.config_path,
                **backup_file,
                tuple_info={'element_index': -1,
                            'possible_values': [
                                'None', 'entry_date', 'entry_price',
                                'entry_time', 'exit_date', 'exit_price',
                                'exit_time', 'size', 'symbol', 'trade_style',
                                'trade_type']}):
            return

        sys.exit(1)
    elif args.C:
        default_config = configure(trade, can_interpolate=False,
                                   can_override=False)
        configuration.check_config_changes(default_config, trade.config_path,
                                           excluded_sections=('Variables',),
                                           **backup_file)
        return
    else:
        config = configure(trade)

    if args.m:
        insert_maintenance_schedules(trade, config)
    if any((args.s, args.y, args.q, args.o)):
        driver = browser_driver.initialize(
            headless=config['General'].getboolean('headless'),
            user_data_directory=config['General']['user_data_directory'],
            profile_directory=config['General']['profile_directory'],
            implicitly_wait=float(config['General']['implicitly_wait']))
        if args.s:
            browser_driver.execute_action(
                driver, config[trade.actions_title]['replace_sbi_securities'])
        if args.y:
            for watchlist in convert_to_yahoo_finance(trade, config):
                config['Variables']['watchlist'] = watchlist
                action = config[trade.actions_title]['export_to_yahoo_finance']
                action = action.replace('\\', '\\\\')
                action = action.replace('\\\\\\\\', '\\\\')
                browser_driver.execute_action(driver, action)
        if args.q:
            check_daily_sales_order_quota(trade, config, driver)
        if args.o:
            browser_driver.execute_action(
                driver, config[trade.actions_title]['get_order_status'])
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
    if args.W:
        if process_utilities.is_running(trade.process):
            print(trade.process, 'is running.')
            sys.exit(1)
        else:
            config[trade.process] = config[trade.process]
            file_utilities.backup_file(config[trade.process]['settings'],
                                       number_of_backups=8)
            remove_watchlists(config[trade.process]['settings'])

def configure(trade, can_interpolate=True, can_override=True):
    if can_interpolate:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
    else:
        config = configparser.ConfigParser()

    config['General'] = {
        'headless': 'True',
        'user_data_directory':
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
        'profile_directory': 'Default',
        'implicitly_wait': '4',
        'csv_directory': os.path.join(os.path.expanduser('~'), 'Downloads'),
        'email_message_from': '',
        'email_message_to': '',
        'fingerprint': ''}
    all_service_name = 'すべてのサービス'
    config[trade.maintenance_schedules_title] = {
        'url':
        ('https://search.sbisec.co.jp/v2/popwin/info/home'
         '/pop6040_maintenance.html'),
        'time_zone': 'Asia/Tokyo',
        'last_inserted': '',
        'calendar_id': '',
        'all_service_xpath':
        ('//p[contains(@class, "mt-x-2") '
         'and text()="ログイン後のすべてのサービスをご利用いただけません。"]'),
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
    config[trade.daily_sales_order_quota_title] = {
        'quota_watchlist': '',
        'sufficient': '◎（余裕あり）'}
    config[trade.order_status_title] = {
        'output_columns':
        ('entry_date', 'None', 'None', 'entry_time', 'symbol', 'size',
         'trade_type', 'trade_style', 'entry_price', 'None', 'None',
         'exit_date', 'exit_time', 'exit_price'),
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
        os.path.join(os.path.expandvars('%APPDATA%'), trade.brokerage,
                     trade.process),
        'settings': '',
        'watchlists': '',
        'backup_directory': '',
        'snapshot_directory':
        os.path.join(os.path.expanduser('~'), 'Downloads')}
    config[trade.actions_title] = {
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
        'export_to_yahoo_finance':
        [('get', 'https://finance.yahoo.com/portfolios'),
         ('exist', ('//*[@id="Col1-0-Portfolios-Proxy"]'
                    '//a[text()="${Variables:watchlist}"]'),
          [('click', ('//*[@id="Col1-0-Portfolios-Proxy"]'
                      '//a[text()="${Variables:watchlist}"]')),
           ('click', '//span[text()="Settings"]'),
           ('sleep', '0.8'),
           ('click', '//span[text()="Delete Portfolio"]'),
           ('click', '//span[text()="Confirm"]')]),
         ('click', '//span[text()="Import"]'),
         ('send_keys', '//input[@name="ext_pf"]',
          r'${General:csv_directory}\${Variables:watchlist}.csv'),
         ('click', '//span[text()="Submit"]'),
         ('refresh',),
         ('sleep', '0.8'),
         ('click', '//a[text()="Imported from Yahoo"]'),
         ('click', '//span[text()="Settings"]'),
         ('click', '//span[text()="Rename Portfolio"]'),
         ('clear', '//input[@value="Imported from Yahoo"]'),
         ('send_keys', '//input[@value="Imported from Yahoo"]',
          '${Variables:watchlist}'),
         ('click', '//span[text()="Save"]'),
         ('sleep', '0.8')],
        'get_daily_sales_order_quota':
        [('get', 'https://www.sbisec.co.jp/ETGate'),
         ('sleep', '0.8'),
         ('click', '//input[@name="ACT_login"]'),
         ('for', "${Variables:securities_codes}",
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
    config['Variables'] = {
        'watchlist': '',
        'securities_codes': ''}

    if can_override:
        config.read(trade.config_path, encoding='utf-8')

    if trade.process == 'HYPERSBI2':
        section = config[trade.process]
        if not section.get('settings') or not section.get('watchlists'):
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
                section['settings'] = os.path.join(
                    application_data_directory, identifier, 'setting.json')
                section['watchlists'] = os.path.join(
                    application_data_directory, identifier, 'portfolio.json')
            else:
                print('Unspecified identifier.')
                sys.exit(1)

    return config

def insert_maintenance_schedules(trade, config):
    def replace_datetime(match):
        matched_year = match.group(int(section['year_group']))
        matched_month = match.group(int(section['month_group']))
        matched_day = match.group(int(section['day_group']))
        matched_time = match.group(int(section['time_group']))
        if matched_year:
            return (f'{matched_year}-{matched_month}-{matched_day} '
                    f'{matched_time}')

        event_datetime = tzinfo.localize(datetime.strptime(
            f'{current_year}-{matched_month}-{matched_day} {matched_time}',
            '%Y-%m-%d %H:%M'))
        timedelta_obj = event_datetime - now
        threshold = timedelta(days=365 - time_frame)
        assumed_year = current_year
        if timedelta_obj < -threshold:
            assumed_year = str(int(current_year) + 1)
        elif timedelta_obj > threshold:
            assumed_year = str(int(current_year) - 1)
        return f'{assumed_year}-{matched_month}-{matched_day} {matched_time}'

    def dict_to_tuple(d):
        if isinstance(d, dict):
            items = []
            for key, value in sorted(d.items()):
                items.append((key, dict_to_tuple(value)))
            return tuple(items)
        return d

    section = config[trade.maintenance_schedules_title]
    # url = section['url']
    # time_zone = section['time_zone']
    last_inserted = section['last_inserted']
    calendar_id = section['calendar_id']
    service_xpath = section['service_xpath']
    datetime_regex = section['datetime_regex']
    previous_bodies = configuration.evaluate_value(section['previous_bodies'])

    head = requests.head(section['url'])
    try:
        head.raise_for_status()
    except Exception as e:
        print(e)
        sys.exit(1)

    tzinfo = pytz.timezone(section['time_zone'])
    now = datetime.now(tzinfo)
    section['last_inserted'] = now.isoformat()

    lower_bound = now - timedelta(days=29)
    if (not last_inserted
        or datetime.fromisoformat(last_inserted) < lower_bound):
        last_inserted = lower_bound
    else:
        last_inserted = datetime.fromisoformat(last_inserted)

    if last_inserted < parsedate_to_datetime(head.headers['last-modified']):
        response = requests.get(section['url'])
        response.encoding = chardet.detect(response.content)['encoding']
        text = response.text
        root = html.fromstring(text)
        matched = re.search('<title>(.*)</title>', text)
        if matched:
            title = matched.group(1)

        credentials = get_credentials(os.path.join(trade.config_directory,
                                                   'token.json'))
        resource = build('calendar', 'v3', credentials=credentials)

        if not section['calendar_id']:
            body = {'summary': trade.maintenance_schedules_title,
                    'timeZone': section['time_zone']}
            try:
                calendar = resource.calendars().insert(body=body).execute()
                section['calendar_id'] = calendar_id = calendar['id']
            except HttpError as e:
                print(e)
                sys.exit(1)

        current_year = now.strftime('%Y')
        time_frame = 30

        try:
            all_service_element = root.xpath(section['all_service_xpath'])[0]
            match = re.search(r'//(\w+)', service_xpath)
            if match:
                pre_element = Element(match.group(1))
                match = re.search(r'@class, +\"(.+?)\"', service_xpath)
                if match:
                    pre_element.set('class', match.group(1))
                    pre_element.text = section['all_service_name']
                    all_service_element.addprevious(pre_element)
        except IndexError:
            pass

        for service in configuration.evaluate_value(section['services']):
            for schedule in root.xpath(service_xpath.format(service)):
                function = schedule.xpath(
                    section['function_xpath'])[0].xpath('normalize-space(text())')
                datetimes = schedule.xpath(
                    section['datetime_xpath'])[0].text_content().split('\n')

                for i in range(len(datetimes)):
                    datetime_range = re.split(
                        re.compile(section['range_splitter_regex']),
                        datetimes[i].strip())

                    if len(datetime_range) == 2:
                        if re.fullmatch(r'\d{1,2}:\d{2}', datetime_range[0]):
                            datetime_str = (start.strftime('%Y-%m-%d ')
                                            + datetime_range[0])
                        else:
                            datetime_str = re.sub(datetime_regex,
                                                  replace_datetime,
                                                  datetime_range[0])

                        start = tzinfo.localize(
                            datetime.strptime(datetime_str, '%Y-%m-%d %H:%M'))

                        if re.fullmatch(r'\d{1,2}:\d{2}', datetime_range[1]):
                            datetime_str = (start.strftime('%Y-%m-%d ')
                                            + datetime_range[1])
                        else:
                            datetime_str = re.sub(datetime_regex,
                                                  replace_datetime,
                                                  datetime_range[1])

                        end = tzinfo.localize(
                            datetime.strptime(datetime_str, '%Y-%m-%d %H:%M'))

                        body = {'summary':
                                f'🛠️ {service}: {function}',
                                'start': {'dateTime': start.isoformat()},
                                'end': {'dateTime': end.isoformat()},
                                'source': {'title': title, 'url': section['url']}}
                        body_tuple = dict_to_tuple(body)

                        if body_tuple not in previous_bodies.get(service, []):
                            try:
                                event = resource.events().insert(
                                    calendarId=calendar_id, body=body
                                ).execute()
                                print(event.get('start')['dateTime'],
                                      event.get('summary'))
                            except HttpError as e:
                                print(e)
                                sys.exit(1)

                            previous_bodies.setdefault(service, []).append(
                                body_tuple)
                            maximum_number_of_bodies = 32
                            if (len(previous_bodies[service])
                                > maximum_number_of_bodies):
                                previous_bodies[service] = previous_bodies[
                                    service][-maximum_number_of_bodies:]

                            section['previous_bodies'] = str(previous_bodies)

        configuration.write_config(config, trade.config_path)

def convert_to_yahoo_finance(trade, config):
    with open(config[trade.process]['watchlists']) as f:
        dictionary = json.load(f)

    csv_directory = config['General']['csv_directory']
    file_utilities.check_directory(csv_directory)
    watchlists = []
    HEADER = ['Symbol', 'Current Price', 'Date', 'Time', 'Change', 'Open',
              'High', 'Low', 'Volume', 'Trade Date', 'Purchase Price',
              'Quantity', 'Commission', 'High Limit', 'Low Limit', 'Comment']
    row = []
    for _ in range(len(HEADER) - 1):
        row.append('')
    for index in range(len(dictionary['list'])):
        watchlist = dictionary['list'][index]['listName']
        csv_file = open(os.path.join(csv_directory, watchlist + '.csv'), 'w')
        writer = csv.writer(csv_file)
        writer.writerow(HEADER)
        dictionary['list'][index]['secList'].reverse()
        for item in dictionary['list'][index]['secList']:
            if item['secKbn'] == 'ST':
                if item['marketCd'] == 'TKY':
                    writer.writerow([item['secCd'] + '.T'] + row)
                elif item['marketCd'] == 'SPR':
                    writer.writerow([item['secCd'] + '.S'] + row)
                elif item['marketCd'] == 'NGY':
                    # Yahoo Finance does not appear to have stocks listed
                    # solely on the Nagoya Stock Exchange.
                    writer.writerow([item['secCd'] + '.N'] + row)
                elif item['marketCd'] == 'FKO':
                    writer.writerow([item['secCd'] + '.F'] + row)

        csv_file.close()
        watchlists.append(watchlist)
    return watchlists

def check_daily_sales_order_quota(trade, config, driver):
    with open(config[trade.process]['watchlists']) as f:
        watchlists = json.load(f)

    quota_section = config[trade.daily_sales_order_quota_title]
    quota_watchlist = next(
        (watchlist for watchlist in watchlists['list']
         if watchlist['listName'] == quota_section['quota_watchlist']), None)
    if quota_watchlist is None:
        print('No matching watchlist was found.')
        sys.exit(1)

    securities_codes = [item['secCd'] for item in quota_watchlist['secList']]
    config['Variables']['securities_codes'] = ', '.join(securities_codes)

    text = []
    browser_driver.execute_action(
        driver, config[trade.actions_title]['get_daily_sales_order_quota'],
        text=text)

    status = ''
    for index, _ in enumerate(text):
        if not quota_section['sufficient'] in text[index]:
            status += f'{securities_codes[index]}: {text[index]}\n'

    print(status)

    general_section = config['General']
    email_message_from = general_section['email_message_from']
    email_message_to = general_section['email_message_to']

    if email_message_from and email_message_to and status:
        credentials = get_credentials(os.path.join(trade.config_directory,
                                                   'token.json'))
        resource = build('gmail', 'v1', credentials=credentials)

        email_message = EmailMessage()
        email_message['Subject'] = trade.daily_sales_order_quota_title
        email_message['From'] = email_message_from
        email_message['To'] = email_message_to
        email_message.set_content(status)

        body = {'raw': base64.urlsafe_b64encode(
            email_message.as_bytes()).decode()}
        try:
            resource.users().messages().send(userId='me', body=body).execute()
        except HttpError as e:
            print(e)
            sys.exit(1)

# TODO
def extract_order_status(trade, config, driver):
    section = config[trade.order_status_title]
    output_columns = configuration.evaluate_value(section['output_columns'])
    table_identifier = section['table_identifier']
    symbol_regex = section['symbol_regex']
    symbol_replacement = section['symbol_replacement']
    margin_trading = section['margin_trading']
    buying_on_margin = section['buying_on_margin']
    execution_column = int(section['execution_column'])
    execution = section['execution']
    datetime_column = int(section['datetime_column'])
    datetime_regex = section['datetime_regex']
    date_replacement = section['date_replacement']
    time_replacement = section['time_replacement']
    size_column = int(section['size_column'])
    price_column = int(section['price_column'])

    try:
        dfs = pd.read_html(StringIO(driver.page_source),
                           match=table_identifier, flavor='lxml')
    except Exception as e:
        print(e)
        sys.exit(1)

    index = 0
    df = dfs[1]
    size_price = pd.DataFrame(columns=('size', 'price'))
    results = pd.DataFrame(columns=output_columns)
    while index < len(df):
        if df.iloc[index, execution_column] == execution:
            if len(size_price) == 0:
                size_price.loc[0] = [df.iloc[index - 1, size_column],
                                     df.iloc[index - 1, price_column]]

            size_price.loc[len(size_price)] = [df.iloc[index, size_column],
                                               df.iloc[index, price_column]]
            if index + 1 == len(df) \
               or df.iloc[index + 1, execution_column] != execution:
                size_price_index = 0
                size_price = size_price.astype(float)
                summation = 0
                while size_price_index < len(size_price):
                    summation += \
                        size_price.loc[size_price_index, 'size'] \
                        * size_price.loc[size_price_index, 'price']
                    size_price_index += 1

                average_price = summation / size_price['size'].sum()
                if margin_trading \
                   in df.iloc[index - len(size_price), execution_column]:
                    entry_price = average_price
                else:
                    results.loc[len(results) - 1, 'exit_price'] = average_price

                size_price = pd.DataFrame(columns=('size', 'price'))

            index += 1
        else:
            symbol = re.sub(symbol_regex, symbol_replacement,
                            df.iloc[index, execution_column])
            size = df.iloc[index + 1, size_column]
            trade_style = 'day'
            if margin_trading in df.iloc[index + 1, execution_column]:
                entry_date = re.sub(datetime_regex, date_replacement,
                                    df.iloc[index + 2, datetime_column])
                entry_time = re.sub(datetime_regex, time_replacement,
                                    df.iloc[index + 2, datetime_column])
                if buying_on_margin in df.iloc[index + 1, execution_column]:
                    trade_type = 'long'
                else:
                    trade_type = 'short'

                entry_price = df.iloc[index + 2, price_column]
            else:
                exit_date = re.sub(datetime_regex, date_replacement,
                                   df.iloc[index + 2, datetime_column])
                exit_time = re.sub(datetime_regex, time_replacement,
                                   df.iloc[index + 2, datetime_column])
                exit_price = df.iloc[index + 2, price_column]

                evaluated_results = []
                for i in range(len(output_columns)):
                    parsed = ast.parse(output_columns[i], mode='eval')
                    fixed = ast.fix_missing_locations(parsed)
                    compiled = compile(fixed, '<string>', 'eval')
                    evaluated_results.append(eval(compiled))

                results.loc[len(results)] = evaluated_results

            index += 3

    if len(results) == 1:
        results = results.reindex([0, 1])

    results.to_clipboard(index=False, header=False)

def remove_watchlists(settings):
    with open(settings, encoding='utf-8') as f:
        dictionary = json.load(f)

    current_template = dictionary['LastSession']['CurrentTemplateId']

    for template in dictionary['LastSession']['Templates']:
        if template['TemplateName'] == current_template:
            windows = template['hyper::stock::ui::WindowManager']['Windows']
            for i in reversed(range(len(windows))):
                if windows[i].get('WindowId') == 'Portfolio':
                    del windows[i]

    with open(settings, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=4)

def get_credentials(token_json):
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
            except Exception as e:
                print(e)
                sys.exit(1)
        with open(token_json, 'w') as token:
            token.write(credentials.to_json())
    return credentials

if __name__ == '__main__':
    main()

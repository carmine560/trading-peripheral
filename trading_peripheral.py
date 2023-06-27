import argparse
import ast
import configparser
import inspect
import os
import re
import sys

import browser_driver
import configuration
import file_utilities
import process_utilities

class Trade:
    def __init__(self, brokerage, process):
        self.brokerage = brokerage
        self.process = process
        self.config_directory = os.path.join(
            os.path.expandvars('%LOCALAPPDATA%'),
            os.path.basename(os.path.dirname(__file__)))
        self.script_base = os.path.splitext(os.path.basename(__file__))[0]
        self.config_path = os.path.join(self.config_directory,
                                        self.script_base + '.ini')

        file_utilities.check_directory(self.config_directory)

        self.daily_sales_order_quota_section = (
            self.brokerage + ' Daily Sales Order Quota')
        self.order_status_section = self.brokerage + ' Order Status'
        self.maintenance_schedules_section = (
            self.brokerage + ' Maintenance Schedules')
        self.action_section = self.process + ' Actions'
        self.categorized_keys = {
            'all_keys': file_utilities.extract_commands(
                inspect.getsource(browser_driver.execute_action)),
            'boolean_keys': ('exist',),
            'additional_value_keys': ('send_keys',),
            'no_value_keys': ('refresh',)}

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-P', default=('SBI Securities', 'HYPERSBI2'),
        metavar=('BROKERAGE', 'PROCESS'), nargs=2,
        help='set the brokerage and the process [defaults: %(default)s]')
    parser.add_argument(
        '-w', action='store_true',
        help='backup the Hyper SBI 2 watchlists')
    parser.add_argument(
        '-s', action='store_true',
        help='replace the watchlists on the SBI Securities website '
        'with the Hyper SBI 2 watchlists')
    parser.add_argument(
        '-y', action='store_true',
        help='export the Hyper SBI 2 watchlists to My Portfolio '
        'on Yahoo Finance')
    parser.add_argument(
        '-q', action='store_true',
        help='check the status of the daily sales order quota '
        'for general margin trading for the specified Hyper SBI 2 watchlist')
    parser.add_argument(
        '-o', action='store_true',
        help='extract the order status from the SBI Securities web page '
        'and copy it to the clipboard')
    parser.add_argument(
        '-m', action='store_true',
        help='insert maintenance schedules into Google Calendar')
    parser.add_argument(
        '-d', action='store_true',
        help='take a snapshot of the Hyper SBI 2 application data')
    parser.add_argument(
        '-D', action='store_true',
        help='restore the Hyper SBI 2 application data from a snapshot')
    group.add_argument(
        '-G', action='store_const', const='General',
        help='configure general options and exit')
    group.add_argument(
        '-O', action='store_const', const='Order Status',
        help='configure order state formats and exit')
    group.add_argument(
        '-M', action='store_const', const='Maintenance Schedules',
        help='configure maintenance schedules and exit')
    group.add_argument(
        '-A', action='store_const', const='Actions',
        help='configure actions and exit')
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    trade = Trade(*args.P)
    backup_file = {'backup_function': file_utilities.backup_file,
                   'backup_parameters': {'number_of_backups': 8}}

    if args.G or args.O or args.M or args.A:
        config = configure(trade, interpolation=False)
        if args.G and configuration.modify_section(
                config, args.G, trade.config_path, **backup_file,
                categorized_keys=trade.categorized_keys):
            return
        elif args.O and configuration.modify_section(
                config, trade.brokerage + ' ' + args.O, trade.config_path,
                **backup_file, categorized_keys=trade.categorized_keys,
                tuple_info={'element_index': -1,
                            'possible_values': [
                                'None', 'entry_date', 'entry_price',
                                'entry_time', 'exit_date', 'exit_price',
                                'exit_time', 'size', 'symbol', 'trade_style',
                                'trade_type']}):
            return
        elif args.M and configuration.modify_section(
                config, trade.brokerage + ' ' + args.M, trade.config_path,
                **backup_file, categorized_keys=trade.categorized_keys):
            return
        elif args.A and configuration.modify_section(
                config, trade.process + ' ' + args.A, trade.config_path,
                **backup_file, categorized_keys=trade.categorized_keys):
            return

        sys.exit(1)
    else:
        config = configure(trade)

    if args.w:
        if config.has_section(trade.process):
            section = config[trade.process]
            file_utilities.backup_file(
                section['watchlists'],
                backup_directory=section['watchlist_backup_directory'])
        else:
            print(trade.process, 'section does not exist')
            sys.exit(1)
    if args.s or args.y or args.q or args.o:
        if config.has_section(trade.action_section):
            section = config['General']
            driver = browser_driver.initialize(
                headless=section.getboolean('headless'),
                user_data_directory=section['user_data_directory'],
                profile_directory=section['profile_directory'],
                implicitly_wait=float(section['implicitly_wait']))
            section = config[trade.action_section]
            if args.s:
                browser_driver.execute_action(
                    driver,
                    ast.literal_eval(section['replace_sbi_securities']))
            if args.y:
                watchlists = convert_to_yahoo_finance(trade, config)
                for watchlist in watchlists:
                    config['Variables']['watchlist'] = watchlist
                    browser_driver.execute_action(
                        driver,
                        ast.literal_eval(section['export_to_yahoo_finance']
                                         .replace('\\', '\\\\')
                                         .replace('\\\\\\\\', '\\\\')))
            if args.q:
                # TODO
                check_daily_sales_order_quota(trade, config, driver)
            if args.o:
                browser_driver.execute_action(
                    driver, ast.literal_eval(section['get_order_status']))
                extract_order_status(trade, config, driver)

            driver.quit()
        else:
            print(trade.action_section, 'section does not exist')
            sys.exit(1)
    if args.m:
        if config.has_section(trade.maintenance_schedules_section):
            insert_maintenance_schedules(trade, config)
        else:
            print(trade.maintenance_schedules_section,
                  'section does not exist')
            sys.exit(1)
    if args.d or args.D:
        if process_utilities.is_running(trade.process):
            print(trade.process, 'is running')
            sys.exit(1)
        elif config.has_section(trade.process):
            section = config[trade.process]
            application_data_directory = section['application_data_directory']
            snapshot_directory = section['snapshot_directory']
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
        else:
            print(trade.process, 'section does not exist')
            sys.exit(1)

def configure(trade, interpolation=True):
    if interpolation:
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
        'scopes': ['https://www.googleapis.com/auth/calendar'],
        'fingerprint': ''}
    config['SBI Securities Daily Sales Order Quota'] = {
        'quota_watchlist': '',
        'there_is_room': '◎（余裕あり）'}
    config['SBI Securities Order Status'] = {
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
        'datetime_pattern': r'^(\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})$$',
        'date_replacement': r'\1',
        'time_replacement': r'\2',
        'size_column': '6',
        'price_column': '7'}
    config['SBI Securities Maintenance Schedules'] = {
        'url': 'https://search.sbisec.co.jp/v2/popwin/info/home/pop6040_maintenance.html',
        'time_zone': 'Asia/Tokyo',
        'last_inserted': '',
        'encoding': 'shift_jis',
        'date_splitter': '<br>',
        'calendar_id': '',
        'services': ('HYPER SBI 2',),
        'service_header': '対象サービス',
        'function_header': 'メンテナンス対象機能',
        'schedule_header': 'メンテナンス予定時間',
        'intraday_splitter': '、',
        'range_splitter': '〜',
        'datetime_pattern': r'^(\d{1,2})/(\d{1,2})（.）(\d{1,2}:\d{2})$$',
        'datetime_replacement': r'\1-\2 \3'}
    config['HYPERSBI2'] = {
        'application_data_directory':
        os.path.join(os.path.expandvars('%APPDATA%'), trade.brokerage,
                     trade.process),
        'watchlists': '',
        'watchlist_backup_directory': '',
        'snapshot_directory':
        os.path.join(os.path.expanduser('~'), 'Downloads')}
    config['HYPERSBI2 Actions'] = {
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
         ('exist', '//*[@id="Col1-0-Portfolios-Proxy"]//a[text()="${Variables:watchlist}"]',
          [('click', '//*[@id="Col1-0-Portfolios-Proxy"]//a[text()="${Variables:watchlist}"]'),
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
        # TODO
        'get_daily_sales_order_quota':
        [('get', 'https://www.sbisec.co.jp/ETGate'),
         ('sleep', '0.8'),
         ('click', '//input[@name="ACT_login"]'),
         ('for', "${Variables:securities_codes}",
          [('send_keys', '//*[@id="top_stock_sec"]'),
           ('click', '//*[@id="srchK"]/a/img'),
           ('click', '//a[text()="信用売"]'),
           ('text', '//*[@id="normal"]/tbody/tr[3]/td/table/tbody/tr[2]/td')])],
        'get_order_status':
        [('get', 'https://www.sbisec.co.jp/ETGate'),
         ('sleep', '0.8'),
         ('click', '//input[@name="ACT_login"]'),
         ('click', '//a[text()="注文照会"]')]}
    config['Variables'] = {
        'watchlist': '',
        'securities_codes': ''}
    config.read(trade.config_path, encoding='utf-8')

    if trade.process == 'HYPERSBI2':
        section = config[trade.process]
        if not section['watchlists']:
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
                print('unspecified identifier')
                sys.exit(1)

    return config

def convert_to_yahoo_finance(trade, config):
    import csv
    import json

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
                    # Yahoo Finance does not seem to have any stocks listed
                    # solely on the Nagoya Stock Exchange.
                    writer.writerow([item['secCd'] + '.N'] + row)
                elif item['marketCd'] == 'FKO':
                    writer.writerow([item['secCd'] + '.F'] + row)

        csv_file.close()
        watchlists.append(watchlist)
    return watchlists

# TODO
def check_daily_sales_order_quota(trade, config, driver):
    import json

    with open(config[trade.process]['watchlists']) as f:
        watchlists = json.load(f)

    section = config[trade.daily_sales_order_quota_section]

    quota_watchlist = next(
        (watchlist for watchlist in watchlists['list']
         if watchlist['listName'] == section['quota_watchlist']), None)
    if quota_watchlist is None:
        print('No matching watchlist was found.')
        sys.exit(1)

    securities_codes = [item['secCd'] for item in quota_watchlist['secList']]
    config['Variables']['securities_codes'] = ', '.join(securities_codes)

    text = []
    browser_driver.execute_action(
        driver,
        ast.literal_eval(
            config[trade.action_section]['get_daily_sales_order_quota']),
        text=text)

    there_is_room = section['there_is_room']
    for index, df in enumerate(text):
        if not there_is_room in text[index]:
            print(securities_codes[index], text[index])

# TODO
def extract_order_status(trade, config, driver):
    import pandas as pd

    section = config[trade.order_status_section]
    output_columns = ast.literal_eval(section['output_columns'])
    table_identifier = section['table_identifier']
    symbol_regex = section['symbol_regex']
    symbol_replacement = section['symbol_replacement']
    margin_trading = section['margin_trading']
    buying_on_margin = section['buying_on_margin']
    execution_column = int(section['execution_column'])
    execution = section['execution']
    datetime_column = int(section['datetime_column'])
    datetime_pattern = section['datetime_pattern']
    date_replacement = section['date_replacement']
    time_replacement = section['time_replacement']
    size_column = int(section['size_column'])
    price_column = int(section['price_column'])

    try:
        dfs = pd.read_html(driver.page_source, match=table_identifier,
                           flavor='lxml')
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
                entry_date = re.sub(datetime_pattern, date_replacement,
                                    df.iloc[index + 2, datetime_column])
                entry_time = re.sub(datetime_pattern, time_replacement,
                                    df.iloc[index + 2, datetime_column])
                if buying_on_margin in df.iloc[index + 1, execution_column]:
                    trade_type = 'long'
                else:
                    trade_type = 'short'

                entry_price = df.iloc[index + 2, price_column]
            else:
                exit_date = re.sub(datetime_pattern, date_replacement,
                                   df.iloc[index + 2, datetime_column])
                exit_time = re.sub(datetime_pattern, time_replacement,
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

def insert_maintenance_schedules(trade, config):
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    import pandas as pd
    import requests

    scopes = ast.literal_eval(config['General']['scopes'])

    section = config[trade.maintenance_schedules_section]
    url = section['url']
    time_zone = section['time_zone']
    last_inserted = section['last_inserted']
    encoding = section['encoding']
    date_splitter = section['date_splitter']
    calendar_id = section['calendar_id']
    services = ast.literal_eval(section['services'])
    service_header = section['service_header']
    function_header = section['function_header']
    schedule_header = section['schedule_header']
    intraday_splitter = section['intraday_splitter']
    range_splitter = section['range_splitter']
    datetime_pattern = section['datetime_pattern']
    datetime_replacement = section['datetime_replacement']

    head = requests.head(url)
    try:
        head.raise_for_status()
    except Exception as e:
        print(e)
        sys.exit(1)

    now = pd.Timestamp.now(tz=time_zone)
    section['last_inserted'] = now.isoformat()
    lower_bound = now - pd.Timedelta(days=29)
    if not last_inserted or pd.Timestamp(last_inserted) < lower_bound:
        last_inserted = lower_bound
    else:
        last_inserted = pd.Timestamp(last_inserted)

    # Assume that all schedules are updated at the same time.
    if last_inserted < pd.Timestamp(head.headers['last-modified']):
        response = requests.get(url)
        response.encoding = encoding
        html = response.text
        matched = re.search('<title>(.*)</title>', html)
        if matched:
            title = matched.group(1)

        html = html.replace(date_splitter, 'DATE_SPLITTER')
        try:
            dfs = pd.read_html(html, match='|'.join(services), flavor='lxml',
                               header=0)
        except Exception as e:
            print(e)
            if re.match('No tables found matching regex', str(e)):
                configuration.write_config(config, trade.config_path)
                return
            else:
                sys.exit(1)

        credentials = get_credentials(
            os.path.join(trade.config_directory, 'token.json'), scopes)
        resource = build('calendar', 'v3', credentials=credentials)

        if not section['calendar_id']:
            body = {'summary': trade.maintenance_schedules_section,
                    'timeZone': time_zone}
            try:
                calendar = resource.calendars().insert(body=body).execute()
                section['calendar_id'] = calendar_id = calendar['id']
            except HttpError as e:
                print(e)
                sys.exit(1)

        year = now.strftime('%Y')
        time_frame = 30

        for service in services:
            for index, df in enumerate(dfs):
                # Assume the first table is for temporary maintenance.
                if (tuple(df.columns.values) ==
                    (service_header, function_header, schedule_header)):
                    df = dfs[index].loc[
                        df[service_header].str.contains(service)]
                    break
            if df.empty:
                break

            function = re.sub(
                '\s*DATE_SPLITTER\s*', ' ', df.iloc[0][function_header])
            dates = df.iloc[0][schedule_header].split('DATE_SPLITTER')
            schedules = []
            for date in dates:
                schedules.extend(date.strip().split(intraday_splitter))

            for i in range(len(schedules)):
                datetime_range = schedules[i].split(range_splitter)

                # Assume that the year of the date is omitted.
                if re.fullmatch('\d{1,2}:\d{2}', datetime_range[0]):
                    datetime = start.strftime('%m-%d ') + datetime_range[0]
                else:
                    datetime = re.sub(datetime_pattern, datetime_replacement,
                                      datetime_range[0])

                start = pd.Timestamp(year + '-' + datetime, tz=time_zone)

                timedelta = pd.Timestamp(start) - now
                threshold = pd.Timedelta(days=365 - time_frame)
                if timedelta < -threshold:
                    year = str(int(year) + 1)
                    start = pd.Timestamp(year + '-' + datetime, tz=time_zone)
                elif timedelta > threshold:
                    year = str(int(year) - 1)
                    start = pd.Timestamp(year + '-' + datetime, tz=time_zone)

                if re.fullmatch('\d{1,2}:\d{2}', datetime_range[1]):
                    end = pd.Timestamp(start.strftime('%Y-%m-%d') + ' '
                                       + datetime_range[1], tz=time_zone)
                else:
                    datetime = re.sub(datetime_pattern, datetime_replacement,
                                      datetime_range[1])
                    end = pd.Timestamp(year + '-' + datetime, tz=time_zone)

                body = {'summary': '🛠️ ' \
                        + service + ' ' + function,
                        'start': {'dateTime': start.isoformat()},
                        'end': {'dateTime': end.isoformat()},
                        'source': {'title': title, 'url': url}}
                try:
                    event = resource.events().insert(calendarId=calendar_id,
                                                     body=body).execute()
                    print(event.get('start')['dateTime'], event.get('summary'))
                except HttpError as e:
                    print(e)
                    sys.exit(1)

        configuration.write_config(config, trade.config_path)

def get_credentials(token_json, scopes):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

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

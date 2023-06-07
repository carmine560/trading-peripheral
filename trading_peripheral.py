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
    """A class to represent a trade.

    Attributes:
        brokerage : name of the brokerage
        process : process of the trade
        config_directory : directory where the configuration file is
        stored
        script_base : base name of the script
        config_file : configuration file for the trade
        order_state_section : section for order status
        maintenance_schedule_section : section for maintenance schedules
        action_section : section for actions
        categorized_keys : categorized keys for the trade"""
    def __init__(self, brokerage, process):
        """Initialize a class instance.

        Args:
            brokerage: name of the brokerage
            process: name of the process

        Attributes:
            brokerage : name of the brokerage
            process : name of the process
            config_directory : directory where the configuration file is
            stored
            script_base : base name of the script
            config_file : path to the configuration file
            order_state_section : section name for order status
            maintenance_schedule_section : section name for maintenance
            schedules
            action_section : section name for actions
            categorized_keys : dictionary containing categorized keys"""
        self.brokerage = brokerage
        self.process = process
        self.config_directory = os.path.join(
            os.path.expandvars('%LOCALAPPDATA%'),
            os.path.basename(os.path.dirname(__file__)))
        self.script_base = os.path.splitext(os.path.basename(__file__))[0]
        self.config_file = os.path.join(self.config_directory,
                                        self.script_base + '.ini')

        file_utilities.check_directory(self.config_directory)

        self.order_state_section = self.brokerage + ' Order Status'
        self.maintenance_schedule_section = \
            self.brokerage + ' Maintenance Schedules'
        self.action_section = self.process + ' Actions'
        self.categorized_keys = {
            'all_keys': file_utilities.extract_commands(
                inspect.getsource(browser_driver.execute_action)),
            'boolean_keys': ('exist',),
            'additional_value_keys': ('send_keys',),
            'no_value_keys': ('refresh',)}

def main():
    """Runs various actions based on command line arguments.

    Args:
        None

    Returns:
        None"""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-P', default=('SBI Securities', 'HYPERSBI2'),
        metavar=('BROKERAGE', 'PROCESS'), nargs=2,
        help='set a brokerage and a process [defaults: %(default)s]')
    parser.add_argument(
        '-w', action='store_true',
        help='backup Hyper SBI 2 watchlists')
    parser.add_argument(
        '-s', action='store_true',
        help='replace watchlists on the SBI Securities website '
        'with Hyper SBI 2 watchlists')
    parser.add_argument(
        '-y', action='store_true',
        help='export Hyper SBI 2 watchlists to My Portfolio '
        'on Yahoo Finance')
    parser.add_argument(
        '-o', action='store_true',
        help='extract order status from the SBI Securities web page '
        'and copy them to the clipboard')
    parser.add_argument(
        '-m', action='store_true',
        help='insert maintenance schedules into Google Calendar')
    parser.add_argument(
        '-d', action='store_true',
        help='take a snapshot of Hyper SBI 2 application data')
    parser.add_argument(
        '-D', action='store_true',
        help='restore Hyper SBI 2 application data from a snapshot')
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
                config, args.G, trade.config_file, **backup_file,
                categorized_keys=trade.categorized_keys):
            return
        elif args.O and configuration.modify_section(
                config, trade.brokerage + ' ' + args.O, trade.config_file,
                **backup_file, categorized_keys=trade.categorized_keys,
                tuple_info={'element_index': -1,
                            'possible_values': [
                                'None', 'entry_date', 'entry_price',
                                'entry_time', 'exit_date', 'exit_price',
                                'exit_time', 'size', 'symbol', 'trade_style',
                                'trade_type']}):
            return
        elif args.M and configuration.modify_section(
                config, trade.brokerage + ' ' + args.M, trade.config_file,
                **backup_file, categorized_keys=trade.categorized_keys):
            return
        elif args.A and configuration.modify_section(
                config, trade.process + ' ' + args.A, trade.config_file,
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
    if args.s or args.y or args.o:
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
            if args.o:
                browser_driver.execute_action(
                    driver, ast.literal_eval(section['get_order_status']))
                extract_order_status(trade, config, driver)

            driver.quit()
        else:
            print(trade.action_section, 'section does not exist')
            sys.exit(1)
    if args.m:
        if config.has_section(trade.maintenance_schedule_section):
            insert_maintenance_schedules(trade, config)
        else:
            print(trade.maintenance_schedule_section, 'section does not exist')
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
    """Configures the trade.

    Args:
        trade: Trade object
        interpolation: Whether to use extended interpolation or not

    Returns:
        ConfigParser object with the configuration

    Raises:
        NotImplementedError: If silent animals are used."""
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
        'range_list_separator': '<br>',
        'calendar_id': '',
        'delete_events': 'True',
        'services': ('HYPER SBI 2',),
        'service_header': '対象サービス',
        'function_header': 'メンテナンス対象機能',
        'schedule_header': 'メンテナンス予定時間',
        'range_punctuation': '〜',
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
        'get_order_status':
        [('get', 'https://www.sbisec.co.jp/ETGate'),
         ('sleep', '0.8'),
         ('click', '//input[@name="ACT_login"]'),
         ('click', '//a[text()="注文照会"]')]}
    config['Variables'] = {
        'watchlist': ''}
    config.read(trade.config_file, encoding='utf-8')

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
    """Converts a trade to Yahoo Finance format.

    Args:
        trade: Trade to be converted
        config: Configuration file for the trade

    Returns:
        A list of watchlists

    Raises:
        FileNotFoundError: If the watchlists file is not found
        NotImplementedError: If the animal is silent"""
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
                    # Yahoo Finance does not seem to have any stocks
                    # listed solely on the Nagoya Stock Exchange.
                    writer.writerow([item['secCd'] + '.N'] + row)
                elif item['marketCd'] == 'FKO':
                    writer.writerow([item['secCd'] + '.F'] + row)

        csv_file.close()
        watchlists.append(watchlist)
    return watchlists

# TODO
def extract_order_status(trade, config, driver):
    """Extract order status from a webpage table and return the results
    as a pandas DataFrame.

    Args:
        trade : trade object
        config : configuration object
        driver : webdriver object

    Returns:
        A pandas DataFrame containing the extracted order status

    Raises:
        Exception: If there is an error while extracting the order
        status from the webpage table."""
    import pandas as pd

    section = config[trade.order_state_section]
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
    """Insert maintenance schedules into Google Calendar.

    Args:
        trade: A trade object
        config: A configuration object

    Returns:
        None

    Raises:
        HttpError: If an HTTP error occurs
        ValueError: If the configuration file is invalid
        Exception: If an error occurs"""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    import pandas as pd
    import requests

    scopes = ast.literal_eval(config['General']['scopes'])

    section = config[trade.maintenance_schedule_section]
    url = section['url']
    time_zone = section['time_zone']
    last_inserted = section['last_inserted']
    encoding = section['encoding']
    range_list_separator = section['range_list_separator']
    calendar_id = section['calendar_id']
    delete_events = section.getboolean('delete_events')
    services = ast.literal_eval(section['services'])
    service_header = section['service_header']
    function_header = section['function_header']
    schedule_header = section['schedule_header']
    range_punctuation = section['range_punctuation']
    datetime_pattern = section['datetime_pattern']
    datetime_replacement = section['datetime_replacement']

    head = requests.head(url)
    try:
        head.raise_for_status()
    except Exception as e:
        print(e)
        sys.exit(1)

    now = pd.Timestamp.now(tz=time_zone)
    lower_bound = now - pd.Timedelta(days=29)
    if not last_inserted or pd.Timestamp(last_inserted) < lower_bound:
        last_inserted = lower_bound
    else:
        last_inserted = pd.Timestamp(last_inserted)

    # Assume that all schedules are updated at the same time.
    if last_inserted < pd.Timestamp(head.headers['last-modified']):
        response = requests.get(url)
        apparent_encoding = response.apparent_encoding
        if apparent_encoding:
            response.encoding = apparent_encoding
        else:
            response.encoding = encoding

        html = response.text
        matched = re.search('<title>(.*)</title>', html)
        if matched:
            title = matched.group(1)

        html = html.replace(range_list_separator, 'RANGE_LIST_SEPARATOR')
        try:
            dfs = pd.read_html(html, match='|'.join(services), flavor='lxml',
                               header=0)
        except Exception as e:
            print(e)
            if re.match('No tables found matching regex', str(e)):
                with open(trade.config_file, 'w', encoding='utf-8') as f:
                    config.write(f)

                sys.exit()
            else:
                sys.exit(1)

        credentials = get_credentials(
            os.path.join(trade.config_directory, 'token.json'), scopes)
        resource = build('calendar', 'v3', credentials=credentials)

        if not section['calendar_id']:
            body = {'summary': trade.maintenance_schedule_section,
                    'timeZone': time_zone}
            try:
                calendar = resource.calendars().insert(body=body).execute()
                section['calendar_id'] = calendar_id = calendar['id']
            except HttpError as e:
                print(e)
                sys.exit(1)
        elif delete_events:
            page_token = None
            while True:
                try:
                    events = resource.events().list(
                        calendarId=calendar_id, pageToken=page_token,
                        updatedMin=last_inserted.isoformat()).execute()
                except HttpError as e:
                    print(e)
                    sys.exit(1)
                for event in events['items']:
                    if event['status'] == 'confirmed':
                        try:
                            resource.events().delete(
                                calendarId=calendar_id,
                                eventId=event['id']).execute()
                        except HttpError as e:
                            print(e)
                            sys.exit(1)

                page_token = events.get('nextPageToken')
                if not page_token:
                    break

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

            function = df.iloc[0][function_header]
            schedules = df.iloc[0][schedule_header].split(
                'RANGE_LIST_SEPARATOR')
            schedules = [schedule.strip() for schedule in schedules]

            for i in range(len(schedules)):
                datetime_range = schedules[i].split(range_punctuation)

                # Assume that the year of the date is omitted.
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

        section['last_inserted'] = pd.Timestamp.now(tz=time_zone).isoformat()
        with open(trade.config_file, 'w', encoding='utf-8') as f:
            config.write(f)

def get_credentials(token_json, scopes):
    """Get Google OAuth2 credentials.

    Args:
        token_json: Path to the token JSON file.
        scopes: List of scopes to authorize for the token.

    Returns:
        Credentials object for the authorized token.

    Raises:
        Exception: If there is an error in getting the credentials."""
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

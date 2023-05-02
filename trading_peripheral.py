import ast
import os
import re
import sys

def main():
    import argparse

    import browser_driver
    import configuration
    import file_utilities

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-p', action='store_true',
        help='backup Hyper SBI 2 portfolio.json')
    parser.add_argument(
        '-s', action='store_true',
        help='replace watchlists on the SBI Securities website '
        'with Hyper SBI 2 watchlists')
    parser.add_argument(
        '-y', action='store_true',
        help='export Hyper SBI 2 portfolio.json to My Portfolio '
        'on Yahoo Finance')
    parser.add_argument(
        '-o', action='store_true',
        help='extract order status from the SBI Securities web page '
        'and copy them to the clipboard')
    parser.add_argument(
        '-m', action='store_true',
        help='insert maintenance schedules into Google Calendar')
    group.add_argument(
        '-G', action='store_const', const='General',
        help='configure general options and exit')
    group.add_argument(
        '-O', action='store_const', const='Order Status',
        help='configure order state formats and exit')
    group.add_argument(
        '-A', action='store_const', const='Actions',
        help='configure actions and exit')
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    config_file = os.path.join(
        os.path.expandvars('%LOCALAPPDATA%'),
        os.path.basename(os.path.dirname(__file__)),
        os.path.splitext(os.path.basename(__file__))[0] + '.ini')
    if args.G or args.O or args.A:
        config = configure(config_file, interpolation=False)
        file_utilities.backup_file(config_file, number_of_backups=8)
        configuration.modify_section(config, (args.G or args.O or args.A),
                                     config_file)
        return
    else:
        config = configure(config_file)

    if args.p:
        file_utilities.backup_file(
            config['General']['portfolio'],
            backup_directory=config['General']['portfolio_backup_directory'])
    if args.s or args.y or args.o:
        driver = browser_driver.initialize(
            headless=config.getboolean('General', 'headless'),
            user_data_dir=config['General']['user_data_directory'],
            profile_directory=config['General']['profile_directory'],
            implicitly_wait=float(config['General']['implicitly_wait']))
        if args.s:
            browser_driver.execute_action(
                driver,
                ast.literal_eval(config['Actions']['replace_sbi_securities']))
        if args.y:
            watchlists = convert_to_yahoo_finance(config)
            for watchlist in watchlists:
                config['Variables']['watchlist'] = watchlist
                browser_driver.execute_action(
                    driver,
                    ast.literal_eval(
                        config['Actions']['export_to_yahoo_finance']
                        .replace('\\', '\\\\')
                        .replace('\\\\\\\\', '\\\\')))
        if args.o:
            browser_driver.execute_action(
                driver,
                ast.literal_eval(config['Actions']['get_order_status']))
            extract_order_status(config, driver)

        driver.quit()
    if args.m:
        insert_maintenance_schedules(config, config_file)

def configure(config_file, interpolation=True):
    import configparser

    if interpolation:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
    else:
        config = configparser.ConfigParser()

    config['General'] = \
        {'portfolio': '',
         'portfolio_backup_directory': '',
         'headless': 'True',
         'user_data_directory':
         os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
         'profile_directory': 'Default',
         'implicitly_wait': '4',
         'csv_directory': os.path.join(os.path.expanduser('~'), 'Downloads'),
         'token_json': os.path.join(
             os.path.expandvars('%LOCALAPPDATA%'),
             os.path.basename(os.path.dirname(__file__)), 'token.json'),
         'credentials_json': os.path.join(
             os.path.expandvars('%LOCALAPPDATA%'),
             os.path.basename(os.path.dirname(__file__)), 'credentials.json')}
    config['Variables'] = \
        {'watchlist': ''}
    config['Order Status'] = \
        {'output_columns':
         ['entry_date', None, None, 'entry_time', 'symbol', 'size',
          'trade_type', 'trade_style', 'entry_price', None, None, 'exit_date',
          'exit_time', 'exit_price'],
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
    config['Actions'] = \
        {'replace_sbi_securities':
         [('get', 'https://www.sbisec.co.jp/ETGate'),
          ('sleep', '0.8'),
          ('click', '//input[@name="ACT_login"]'),
          ('click', '//a[text()="ポートフォリオ"]'),
          ('click', '//a[text()="登録銘柄リストの追加・置き換え"]'),
          ('click', '//img[@alt="登録銘柄リストの追加・置き換え機能を利用する"]'),
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
          ('send_keys', '//input[@name="ext_pf"]', r'${General:csv_directory}\${Variables:watchlist}.csv'),
          ('click', '//span[text()="Submit"]'),
          ('refresh',),
          ('sleep', '0.8'),
          ('click', '//a[text()="Imported from Yahoo"]'),
          ('click', '//span[text()="Settings"]'),
          ('click', '//span[text()="Rename Portfolio"]'),
          ('clear', '//input[@value="Imported from Yahoo"]'),
          ('send_keys', '//input[@value="Imported from Yahoo"]', '${Variables:watchlist}'),
          ('click', '//span[text()="Save"]'),
          ('sleep', '0.8')],
         'get_order_status':
         [('get', 'https://www.sbisec.co.jp/ETGate'),
          ('sleep', '0.8'),
          ('click', '//input[@name="ACT_login"]'),
          ('click', '//a[text()="注文照会"]')]}
    config['Maintenance Schedules'] = \
        {'url': 'https://search.sbisec.co.jp/v2/popwin/info/home/pop6040_maintenance.html',
         'service': 'HYPER SBI 2', # TODO
         'function_header': 'メンテナンス対象機能',
         'schedule_header': 'メンテナンス予定時間',
         'time_zone': 'Asia/Tokyo',
         'range_punctuation': '〜',
         'datetime_pattern': r'^(\d{1,2})/(\d{1,2})（.）(\d{1,2}:\d{2})$$',
         'datetime_replacement': r'\1-\2 \3',
         'calendar_id': 'primary',
         'last_inserted': '1970-01-01T00:00:00+00:00'}
    config.read(config_file, encoding='utf-8')

    if not config['General']['portfolio']:
        HYPERSBI2_PROFILES = os.path.expandvars(
            r'%APPDATA%\SBI Securities\HYPERSBI2')
        latest_modified_time = 0.0
        identifier = ''
        for f in os.listdir(HYPERSBI2_PROFILES):
            if re.match('^[0-9a-z]{32}$', f):
                modified_time = os.path.getmtime(os.path.join(
                    HYPERSBI2_PROFILES, f))
                if modified_time > latest_modified_time:
                    latest_modified_time = modified_time
                    identifier = f
        if identifier:
            config['General']['portfolio'] = \
                os.path.join(HYPERSBI2_PROFILES, identifier, 'portfolio.json')
        else:
            print('unspecified identifier')
            sys.exit(1)

    return config

def convert_to_yahoo_finance(config):
    import csv
    import json

    with open(config['General']['portfolio']) as f:
        dictionary = json.load(f)

    csv_directory = config['General']['csv_directory']
    if not os.path.isdir(csv_directory):
        try:
            os.makedirs(csv_directory)
        except OSError as e:
            print(e)
            sys.exit(1)

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
def extract_order_status(config, driver):
    import sys

    import pandas as pd

    section = config['Order Status']
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

    dfs = pd.DataFrame()
    try:
        dfs = pd.read_html(driver.page_source, match=table_identifier,
                           flavor='lxml')
    except Exception as e:
        print(e)
        sys.exit(1)

    index = 0
    df = dfs[1]
    size_price = pd.DataFrame(columns=['size', 'price'])
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

                size_price = pd.DataFrame(columns=['size', 'price'])

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
                    if output_columns[i]:
                        parsed = ast.parse(output_columns[i], mode='eval')
                        fixed = ast.fix_missing_locations(parsed)
                        compiled = compile(fixed, '<string>', 'eval')
                        evaluated_results.append(eval(compiled))
                    else:
                        evaluated_results.append(None)

                results.loc[len(results)] = evaluated_results

            index += 3

    if len(results) == 1:
        results = results.reindex([0, 1])

    results.to_clipboard(index=False, header=False)

def insert_maintenance_schedules(config, config_file):
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    import pandas as pd
    import requests

    section = config['Maintenance Schedules']
    url = section['url']
    service = section['service']
    function_header = section['function_header']
    schedule_header = section['schedule_header']
    time_zone = section['time_zone']
    range_punctuation = section['range_punctuation']
    datetime_pattern = section['datetime_pattern']
    datetime_replacement = section['datetime_replacement']
    calendar_id = section['calendar_id']
    last_inserted = section['last_inserted']

    head = requests.head(url)
    try:
        head.raise_for_status()
    except Exception as e:
        print(e)
        sys.exit(1)

    if pd.Timestamp(last_inserted) \
       < pd.Timestamp(head.headers['last-modified']):
        dfs = pd.DataFrame()
        try:
            dfs = pd.read_html(url, match=service, flavor='lxml',
                               header=0, index_col=0)
        except Exception as e:
            print(e)
            sys.exit(1)

        # for service in services:

        df = dfs[len(dfs) - 1].filter(regex=service, axis=0)
        function = df.iloc[0][function_header]
        # FIXME
        schedules = df.iloc[0][schedule_header].split()
        now = pd.Timestamp.now(tz=time_zone)
        time_frame = 30
        year = now.strftime('%Y')

        credentials = get_credentials(config)
        response = requests.get(url)
        response.encoding = response.apparent_encoding
        matched = re.search('<title>(.*)</title>', response.text)
        if matched:
            title = matched.group(1)

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

            if re.match('^\d{1,2}:\d{2}$', datetime_range[1]):
                end = pd.Timestamp(start.strftime('%Y-%m-%d') + ' '
                                   + datetime_range[1], tz=time_zone)
            else:
                datetime = re.sub(datetime_pattern, datetime_replacement,
                                  datetime_range[1])
                end = pd.Timestamp(year + '-' + datetime, tz=time_zone)

            try:
                resource = build('calendar', 'v3', credentials=credentials)
                body = {'summary': '🛠️ ' \
                        + service + ' ' + function,
                        'start': {'dateTime': start.isoformat()},
                        'end': {'dateTime': end.isoformat()},
                        'source': {'title': title, 'url': url}}
                event = resource.events().insert(calendarId=calendar_id,
                                                 body=body).execute()
                print(event.get('start')['dateTime'], event.get('summary'))
            except HttpError as e:
                print(e)
                sys.exit(1)

        section['last_inserted'] = now.isoformat()
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)

def get_credentials(config):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    section = config['General']
    token_json = section['token_json']
    credentials_json = section['credentials_json']

    credentials = None
    # TODO
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    if os.path.exists(token_json):
        credentials = Credentials.from_authorized_user_file(token_json, SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_json, SCOPES)
                credentials = flow.run_local_server(port=0)
            except Exception as e:
                print(e)
                sys.exit(1)
        with open(token_json, 'w') as token:
            token.write(credentials.to_json())

    return credentials

if __name__ == '__main__':
    main()

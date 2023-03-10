import ast
import os
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
    group.add_argument(
        '-C', action='store_const', const='Common',
        help='configure common options and exit')
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
    if args.C or args.O or args.A:
        config = configure(config_file, interpolation=False)
        file_utilities.backup_file(config_file, number_of_backups=8)
        configuration.modify_section(config, (args.C or args.O or args.A),
                                     config_file)
        return
    else:
        config = configure(config_file)

    if args.p:
        file_utilities.backup_file(
            config['Common']['portfolio'],
            backup_directory=config['Common']['portfolio_backup_directory'])
    if args.s or args.y or args.o:
        driver = browser_driver.initialize(
            headless=config.getboolean('Common', 'headless'),
            user_data_dir=config['Common']['user_data_dir'],
            profile_directory=config['Common']['profile_directory'],
            implicitly_wait=float(config['Common']['implicitly_wait']))
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

def configure(config_file, interpolation=True):
    import configparser
    import re

    if interpolation:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
    else:
        config = configparser.ConfigParser()

    config['Common'] = \
        {'portfolio': '',
         'portfolio_backup_directory': '',
         'headless': 'True',
         'user_data_dir':
         os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
         'profile_directory': 'Default',
         'implicitly_wait': '4',
         'csv_directory': os.path.join(os.path.expanduser('~'), 'Downloads')}
    config['Variables'] = \
        {'watchlist': ''}
    config['Order Status'] = \
        {'output_columns':
         ['entry_date', None, None, 'entry_time', 'symbol', 'size',
          'trade_type', 'trade_style', 'entry_price', None, None, 'exit_date',
          'exit_time', 'exit_price'],
         'table_identifier': '????????????',
         'symbol_regex': r'^.* (\d{4}) ??????$$',
         'symbol_replacement': r'\1',
         'margin_trading': '??????',
         'buying_on_margin': '?????????',
         'execution_column': '3',
         'execution': '??????',
         'datetime_column': '5',
         'datetime_regex': r'^(\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})$$',
         'date_replacement': r'\1',
         'time_replacement': r'\2',
         'size_column': '6',
         'price_column': '7'}
    config['Actions'] = \
        {'replace_sbi_securities':
         [('get', 'https://www.sbisec.co.jp/ETGate'),
          ('click', '//input[@name="ACT_login"]'),
          ('click', '//a[text()="?????????????????????"]'),
          ('click', '//a[text()="?????????????????????????????????????????????"]'),
          ('click', '//img[@alt="??????????????????????????????????????????????????????????????????"]'),
          ('click', '//*[@name="tool_from" and @value="3"]'),
          ('click', '//input[@value="??????"]'),
          ('click', '//*[@name="tool_to_1" and @value="1"]'),
          ('click', '//input[@value="??????"]'),
          ('click', '//*[@name="add_replace_tool_01" and @value="1_2"]'),
          ('click', '//input[@value="???????????????"]'),
          ('click', '//input[@value="????????????"]')],
         'export_to_yahoo_finance':
         [('get', 'https://finance.yahoo.com/portfolios'),
          ('exist', '//*[@id="Col1-0-Portfolios-Proxy"]//a[text()="${Variables:watchlist}"]',
           [('click', '//*[@id="Col1-0-Portfolios-Proxy"]//a[text()="${Variables:watchlist}"]'),
            ('click', '//span[text()="Settings"]'),
            ('sleep', '0.8'),
            ('click', '//span[text()="Delete Portfolio"]'),
            ('click', '//span[text()="Confirm"]')]),
          ('click', '//span[text()="Import"]'),
          ('send_keys', '//input[@name="ext_pf"]', r'${Common:csv_directory}\${Variables:watchlist}.csv'),
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
          ('click', '//input[@name="ACT_login"]'),
          ('click', '//a[text()="????????????"]')]}
    config.read(config_file, encoding='utf-8')

    if not config['Common']['portfolio']:
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
            config['Common']['portfolio'] = \
                os.path.join(HYPERSBI2_PROFILES, identifier, 'portfolio.json')
        else:
            print('unspecified identifier')
            sys.exit(1)

    return config

def convert_to_yahoo_finance(config):
    import csv
    import json

    with open(config['Common']['portfolio']) as f:
        dictionary = json.load(f)

    csv_directory = config['Common']['csv_directory']
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
    import re
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
    datetime_regex = section['datetime_regex']
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

if __name__ == '__main__':
    main()

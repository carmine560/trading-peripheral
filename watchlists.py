import os
import sys

def main():
    import argparse
    import ast

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
    group.add_argument(
        '-C', action='store_const', const='Common',
        help='configure common options and exit')
    group.add_argument(
        '-A', action='store_const', const='Actions',
        help='configure actions and exit')
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    config_file = os.path.join(
        os.path.expandvars('%LOCALAPPDATA%'),
        os.path.basename(os.path.dirname(__file__)),
        os.path.splitext(os.path.basename(__file__))[0] + '.ini')
    if args.C or args.A:
        config = configure(config_file, interpolation=False)
        file_utilities.backup_file(config_file, number_of_backups=8)
        configuration.modify_section(config, (args.C or args.A), config_file)
        return
    else:
        config = configure(config_file)

    if args.p:
        file_utilities.backup_file(
            config['Common']['portfolio'],
            backup_directory=config['Common']['portfolio_backup_directory'])
    if args.s or args.y:
        driver = browser_driver.initialize(
            user_data_dir=config['Common']['user_data_dir'],
            profile_directory=config['Common']['profile_directory'])
        if args.s:
            action = ast.literal_eval(
                config['Actions']['replace_sbi_securities'])
            browser_driver.execute_action(driver, action)
        if args.y:
            watchlists = convert_to_yahoo_finance(config)
            for watchlist in watchlists:
                config['Variables']['watchlist'] = watchlist
                action = ast.literal_eval(
                    config['Actions']['export_to_yahoo_finance']
                    .replace('\\', '\\\\')
                    .replace('\\\\\\\\', '\\\\'))
                browser_driver.execute_action(driver, action)

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
         'user_data_dir':
         os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
         'profile_directory': 'Default',
         'csv_directory': os.path.join(os.path.expanduser('~'), 'Downloads')}
    config['Variables'] = \
        {'watchlist': ''}
    config['Actions'] = \
        {'replace_sbi_securities':
         [('get', 'https://www.sbisec.co.jp/ETGate'),
          ('sleep', '1'),
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
            ('click', '//span[text()="Delete Portfolio"]'),
            ('click', '//span[text()="Confirm"]')]),
          ('click', '//span[text()="Import"]'),
          ('send_keys', '//input[@name="ext_pf"]', r'${Common:csv_directory}\${Variables:watchlist}.csv'),
          ('click', '//span[text()="Submit"]'),
          ('refresh',),
          ('click', '//a[text()="Imported from Yahoo"]'),
          ('click', '//span[text()="Settings"]'),
          ('click', '//span[text()="Rename Portfolio"]'),
          ('clear', '//input[@value="Imported from Yahoo"]'),
          ('send_keys', '//input[@value="Imported from Yahoo"]', '${Variables:watchlist}'),
          ('click', '//span[text()="Save"]'),
          ('sleep', '1')]}
    config.read(config_file, encoding='utf-8')

    if not config['Common']['portfolio']:
        HYPERSBI2_PROFILES = os.path.expandvars(
            r'%APPDATA%\SBI Securities\HYPERSBI2')
        identifier = ''
        # TODO
        for f in os.listdir(HYPERSBI2_PROFILES):
            if re.match('^[0-9a-z]{32}$', f):
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

if __name__ == '__main__':
    main()

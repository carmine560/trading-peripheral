import os
import sys

def main():
    import ast
    import re

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    import file_utilities

    config_file = os.path.join(
        os.path.expandvars('%LOCALAPPDATA%'),
        os.path.basename(os.path.dirname(__file__)),
        os.path.splitext(os.path.basename(__file__))[0] + '.ini')
    config = configure(config_file)

    if not config['Common']['portfolio']:
        HYPERSBI2_ROOT = os.path.expandvars(
            r'%APPDATA%\SBI Securities\HYPERSBI2')
        identifier = ''
        # TODO
        for f in os.listdir(HYPERSBI2_ROOT):
            if re.match('^[0-9a-z]{32}$', f):
                identifier = f
        if identifier:
            config['Common']['portfolio'] = \
                os.path.join(HYPERSBI2_ROOT, identifier, 'portfolio.json')
        else:
            print('unspecified identifier')
            sys.exit(1)

    # # TODO
    # file_utilities.backup_file(config_file, number_of_backups=8)
    # with open(config_file, 'w', encoding='utf-8') as f:
    #     config.write(f)

    # file_utilities.backup_file(
    #     config['Common']['portfolio'],
    #     backup_root=config['Common']['portfolio_backup_root'])

    # service = Service(executable_path=ChromeDriverManager().install(),
    #                   log_path=os.path.devnull)
    # options = Options()
    # options.add_argument('--headless=new')
    # options.add_argument('--user-data-dir='
    #                      + config['Common']['user_data_dir'])
    # options.add_argument('--profile-directory='
    #                      + config['Common']['profile_directory'])
    # driver = webdriver.Chrome(service=service, options=options)
    # # TODO
    # driver.implicitly_wait(1)

    # action = ast.literal_eval(
    #     config['Actions']['replace_sbi_securities'])
    # interact_with_browser(driver, action)

    # watchlists = convert_to_yahoo_finance(config)
    # for watchlist in watchlists:
    #     config['Common']['watchlist'] = watchlist
    #     action = ast.literal_eval(config['Actions']['export_to_yahoo_finance']
    #                               .replace('\\', '\\\\')
    #                               .replace('\\\\\\\\', '\\\\'))
    #     interact_with_browser(driver, action)

    # driver.quit()

    update_watchlists(config)

def configure(config_file):
    import configparser

    config = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation())
    config['Common'] = \
        {'portfolio': '',
         'portfolio_backup_root': '',
         'user_data_dir': os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
         'profile_directory': 'Default',
         'csv_root': os.path.join(os.path.expanduser('~'), 'Downloads'),
         'watchlist': ''}
    config['Market Data'] = {
        # TODO
        'market_data': \
        [('Active', 'https://kabutan.jp/warning/?mode=2_9&market=1'),
         ('Limit Up', 'https://kabutan.jp/warning/?mode=3_1&market=0&capitalization=-1&stc=&stm=1&col=zenhiritsu')],
        'symbol_header': 'コード',
        'price_header': '株価',
        'price_limit': '3000'}
    config['Actions'] = \
        {'replace_sbi_securities':
         [('get', 'https://www.sbisec.co.jp/ETGate'),
          ('sleep', '1'),
          ('click', '//*[@id="new_login"]/form/p[2]/input'),
          ('click', '//*[@id="link02M"]/ul/li[1]/a'),
          ('click', '//a[text()="登録銘柄リストの追加・置き換え"]'),
          ('click', '//*[@id="pfcopyinputForm"]/table/tbody/tr/td/div[3]/p/a'),
          ('click', '//*[@name="tool_from" and @value="3"]'),
          ('click', '//input[@value="次へ"]'),
          ('click', '//*[@name="tool_to_1" and @value="1"]'),
          ('click', '//input[@value="次へ"]'),
          ('click', '//*[@name="add_replace_tool_01" and @value="1_2"]'),
          ('click', '//input[@value="確認画面へ"]'),
          ('click', '//input[@value="指示実行"]')],
         'export_to_yahoo_finance':
         [('get', 'https://finance.yahoo.com/portfolios'),
          ('exist', '//*[@id="Col1-0-Portfolios-Proxy"]//a[text()="${Common:watchlist}"]',
           [('click', '//*[@id="Col1-0-Portfolios-Proxy"]//a[text()="${Common:watchlist}"]'),
            ('click', '//*[@id="Lead-3-Portfolios-Proxy"]/main/header/div[2]/div/div/div[3]/div'),
            ('click', '//*[@id="dropdown-menu"]/ul/li[6]/button'),
            ('click', '//*[@id="myLightboxContainer"]/section/form/div[2]/button[1]')]),
          ('click', '//*[@data-test="import-pf-btn"]'),
          ('send_keys', '//*[@id="myLightboxContainer"]/section/form/div[1]/input', r'${Common:csv_root}\${Common:watchlist}.csv'),
          ('click', '//*[@id="myLightboxContainer"]/section/form/div[2]/button[1]'),
          ('refresh',),
          ('click', '//*[@id="Col1-0-Portfolios-Proxy"]/main/table/tbody/tr[1]/td[1]/div[2]/a'),
          ('click', '//*[@id="Lead-3-Portfolios-Proxy"]/main/header/div[2]/div/div/div[3]/div'),
          ('click', '//*[@id="dropdown-menu"]/ul/li[5]/button'),
          ('clear', '//*[@id="myLightboxContainer"]/section/form/div[1]/input'),
          ('send_keys', '//*[@id="myLightboxContainer"]/section/form/div[1]/input', '${Common:watchlist}'),
          ('click', '//*[@id="myLightboxContainer"]/section/form/div[2]/button[1]'),
          ('sleep', '1')]}

    # TODO
    config_home = os.path.dirname(config_file)
    if not os.path.isdir(config_home):
        try:
            os.mkdir(config_home)
        except OSError as e:
            print(e)
            sys.exit(1)

    config.read(config_file, encoding='utf-8')
    return config

def interact_with_browser(driver, action):
    import time

    from selenium.webdriver.common.by import By

    for index in range(len(action)):
        command = action[index][0]
        if len(action[index]) > 1:
            argument = action[index][1]

        if command == 'clear':
            driver.find_element(By.XPATH, argument).clear()
        elif command == 'click':
            driver.find_element(By.XPATH, argument).click()
        elif command == 'exist':
            if driver.find_elements(By.XPATH, argument):
                interact_with_browser(driver, action[index][2])
        elif command == 'get':
            driver.get(argument)
        elif command == 'refresh':
            driver.refresh()
        elif command == 'send_keys':
            driver.find_element(By.XPATH, argument).send_keys(action[index][2])
        elif command == 'sleep':
            time.sleep(int(argument))

def convert_to_yahoo_finance(config):
    import csv
    import json

    with open(config['Common']['portfolio']) as f:
        dictionary = json.load(f)

    csv_root = config['Common']['csv_root']
    if not os.path.isdir(csv_root):
        try:
            os.makedirs(csv_root)
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
        csv_file = open(os.path.join(csv_root, watchlist + '.csv'), 'w')
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

def update_watchlists(config):
    import ast
    import datetime
    import json
    import random
    import re
    import string

    import pandas as pd

    section = config['Market Data']
    market_data = ast.literal_eval(section['market_data'])
    symbol_header = section['symbol_header']
    price_header = section['price_header']
    price_limit = float(section['price_limit'])

    for i in range(len(market_data)):
        title = market_data[i][0]
        url = market_data[i][1]
        if len(market_data[i]) > 2:
            number_of_pages = int(market_data[i][2])
        else:
            number_of_pages = 1

        dfs = []
        for i in range(number_of_pages):
            try:
                dfs = dfs + pd.read_html(url + '&page=' + str(i + 1),
                                         match=symbol_header)
            except Exception as e:
                print(e)
                sys.exit(1)

        df = pd.concat(dfs)
        if price_limit > 0:
            df = df.loc[df[price_header] < price_limit]

        df = df[[symbol_header]]
        df = df.rename(columns={symbol_header: 'secCd'})

        stocks = json.loads(df.to_json(orient='records'))
        for i in range(len(stocks)):
            # TODO
            stocks[i]['marketCd'] = 'TKY'
            stocks[i]['secCd'] = str(stocks[i]['secCd'])
            stocks[i]['secKbn'] = 'ST'
            stocks[i]['sortNo'] = i

        watchlist = {
            "listId":
            re.sub('\D', '',
                   datetime.datetime.now().isoformat(timespec='milliseconds'))
            + ''.join(random.choice(string.ascii_letters + string.digits) \
                      for _ in range(8)),
            "listName": title,
            "secCnt": len(stocks),
            "sortNo": 0
        }
        watchlist['secList'] = stocks

        with open(config['Common']['portfolio'], 'r') as f:
            watchlists = json.load(f)

        watchlists['list'] = \
            [w for w in watchlists['list'] if w['listName'] != title]
        watchlists['list'].append(watchlist)
        watchlists['listCnt'] = len(watchlists['list'])
        for index in range(len(watchlists['list'])):
            watchlists['list'][index]['sortNo'] = index

        with open(config['Common']['portfolio'], 'w') as f:
            json.dump(watchlists, f)

if __name__ == '__main__':
    main()

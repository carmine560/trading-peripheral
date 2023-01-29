import ast
import configparser
import os
import sys
import time

from selenium.webdriver.common.by import By

def main():
    import re

    import file_utilities

    config_file = os.path.join(
        os.path.expandvars('%LOCALAPPDATA%'),
        os.path.basename(os.path.dirname(__file__)),
        os.path.splitext(os.path.basename(__file__))[0] + '.ini')
    config = configure(config_file)
    # TODO
    # file_utilities.backup_file(config_file, number_of_backups=8)
    # with open(config_file, 'w', encoding='utf-8') as f:
    #     config.write(f)

    HYPERSBI2_ROOT = os.path.expandvars(r'%APPDATA%\SBI Securities\HYPERSBI2')
    identifier = ''
    # TODO
    for f in os.listdir(HYPERSBI2_ROOT):
        if re.match('^[0-9a-z]{32}$', f):
            identifier = f
    if identifier:
        portfolio = os.path.join(HYPERSBI2_ROOT, identifier, 'portfolio.json')
    else:
        print('unspecified identifier')
        sys.exit(1)

    file_utilities.backup_file(
        portfolio, backup_root=config['Common']['portfolio_backup_root'])

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    service = Service(executable_path=ChromeDriverManager().install(),
                      log_path=os.path.devnull)
    options = Options()
    # options.add_argument('--headless=new')
    options.add_argument('--user-data-dir='
                         + config['Common']['user_data_dir'])
    options.add_argument('--profile-directory='
                         + config['Common']['profile_directory'])
    driver = webdriver.Chrome(service=service, options=options)
    # TODO
    driver.implicitly_wait(1)

    # action = ast.literal_eval(
    #     config['Actions']['replace_sbi_securities_with_hypersbi2'])
    # interact_with_browser(driver, action)
    # driver.quit()

    # sys.exit()

    # watchlists = convert_to_yahoo_finance(config, portfolio)
    watchlists = ['Favorites']
    for watchlist in watchlists:
        config['Common']['watchlist'] = watchlist
        # config['Common']['watchlist_path'] = os.path.join(config['Common']['csv_root'], watchlist + '.csv')
        # print(os.sep)
        # sys.exit()
        # print(type(config['Actions']['export_to_yahoo_finance']))
        # print(config['Actions']['export_to_yahoo_finance'].replace('\\', '/'))
        # print(config['Actions']['export_to_yahoo_finance'].replace(os.sep, '\\\\'))
        # sys.exit()

        action = ast.literal_eval(config['Actions']['export_to_yahoo_finance'].replace(os.sep, '/'))
        interact_with_browser(driver, action)

    driver.quit()

def configure(config_file):
    config = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation())
    config['Common'] = \
        {'portfolio_backup_root': '',
         'user_data_dir':
         os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
         'profile_directory': 'Default',
         # TODO
         # 'csv_root': os.path.join(os.path.expanduser('~'), 'Downloads').replace(os.sep, '/'),
         'csv_root': os.path.join(os.path.expanduser('~'), 'Downloads'),
         'watchlist': ''}
    config['Actions'] = \
        {'replace_sbi_securities_with_hypersbi2':
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
          # TODO
          # ('send_keys', '//*[@id="myLightboxContainer"]/section/form/div[1]/input', '${Common:csv_root}/${Common:watchlist}.csv'),
          ('send_keys', '//*[@id="myLightboxContainer"]/section/form/div[1]/input', r'${Common:csv_root}\${Common:watchlist}.csv'),
          # ('send_keys', '//*[@id="myLightboxContainer"]/section/form/div[1]/input', '${Common:watchlist_path}'),
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
    # print(action)
    # sys.exit()
    for index in range(len(action)):
        command = action[index][0]
        if len(action[index]) > 1:
            argument = action[index][1]

        if command == 'get':
            driver.get(argument)
            # print(index, command, argument)
        elif command == 'click':
            driver.find_element(By.XPATH, argument).click()
            # print(index, command, argument)
        elif command == 'clear':
            driver.find_element(By.XPATH, argument).clear()
            # print(index, command, argument)
        elif command == 'sleep':
            time.sleep(int(argument))
            # print(index, command, argument)
        elif command == 'exist':
            # print(index, command, argument, action[index][2])
            # print(action[index])
            # if True:
                # subaction = ast.literal_eval(action[index][2])
                # interact_with_browser(driver, subaction)
            if driver.find_elements(By.XPATH, argument):
                interact_with_browser(driver, action[index][2])
        elif command == 'send_keys':
            # print(action[index][2])
            # sys.exit()
            driver.find_element(By.XPATH, argument).send_keys(action[index][2])
            # print(index, command, argument, action[index][2])
        elif command == 'refresh':
            # print(index, command)
            driver.refresh()

def convert_to_yahoo_finance(config, portfolio):
    import csv
    import json

    with open(portfolio) as f:
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

def export_to_yahoo_finance(config, driver):
    # TODO
    csv_root = config['Common']['csv_root']
    watchlist = config['Common']['watchlist']

    driver.get('https://finance.yahoo.com/portfolios')

    elements = driver.find_elements(By.XPATH, '//*[@id="Col1-0-Portfolios-Proxy"]//a[text()="' + watchlist + '"]')
    if elements:
        elements[0].click()
        driver.find_element(By.XPATH, '//*[@id="Lead-3-Portfolios-Proxy"]/main/header/div[2]/div/div/div[3]/div').click()
        driver.find_element(By.XPATH, '//*[@id="dropdown-menu"]/ul/li[6]/button').click()
        driver.find_element(By.XPATH, '//*[@id="myLightboxContainer"]/section/form/div[2]/button[1]').click()

    driver.find_element(By.XPATH, '//*[@data-test="import-pf-btn"]').click()
    driver.find_element(By.XPATH, '//*[@id="myLightboxContainer"]/section/form/div[1]/input').send_keys(os.path.join(csv_root, watchlist + '.csv'))
    driver.find_element(By.XPATH, '//*[@id="myLightboxContainer"]/section/form/div[2]/button[1]').click()
    driver.refresh()
    driver.find_element(By.XPATH, '//*[@id="Col1-0-Portfolios-Proxy"]/main/table/tbody/tr[1]/td[1]/div[2]/a').click()
    driver.find_element(By.XPATH, '//*[@id="Lead-3-Portfolios-Proxy"]/main/header/div[2]/div/div/div[3]/div').click()
    driver.find_element(By.XPATH, '//*[@id="dropdown-menu"]/ul/li[5]/button').click()
    driver.find_element(By.XPATH, '//*[@id="myLightboxContainer"]/section/form/div[1]/input').clear()
    driver.find_element(By.XPATH, '//*[@id="myLightboxContainer"]/section/form/div[1]/input').send_keys(watchlist)
    driver.find_element(By.XPATH, '//*[@id="myLightboxContainer"]/section/form/div[2]/button[1]').click()
    # TODO
    time.sleep(1)

if __name__ == '__main__':
    main()

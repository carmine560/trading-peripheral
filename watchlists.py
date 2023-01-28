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
    with open(config_file, 'w', encoding='utf-8') as f:
        config.write(f)

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

    # TODO
    # file_utilities.backup_file(portfolio,
    #                            os.path.join(
    #                                os.path.expanduser('~'),
    #                                r'Dropbox\Documents\Trading\Backups'))

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    service = Service(executable_path=ChromeDriverManager().install(),
                      log_path=os.path.devnull)
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--user-data-dir=' + os.path.expandvars(
        r'%LOCALAPPDATA%\Google\Chrome\User Data'))
    options.add_argument('--profile-directory=Default')
    driver = webdriver.Chrome(service=service, options=options)
    # TODO
    driver.implicitly_wait(1)

    action = ast.literal_eval(
        config['Actions']['replace_sbi_securities_with_hypersbi2'])
    interact_with_browser(driver, action)
    driver.quit()

    sys.exit()

    csv_root = os.path.join(os.path.expanduser('~'), 'Downloads')
    watchlists = convert_to_yahoo_finance(portfolio, csv_root)
    for watchlist in watchlists:
        export_to_yahoo_finance(driver, csv_root, watchlist)

    driver.quit()

def configure(config_file):
    config = configparser.ConfigParser()
    config['Actions'] = \
        {'replace_sbi_securities_with_hypersbi2':
         [('get',
           'https://www.sbisec.co.jp/ETGate'),
          ('sleep',
           '1'),
          ('click',
           '//*[@id="new_login"]/form/p[2]/input'),
          ('click',
           '//*[@id="link02M"]/ul/li[1]/a'),
          # https://site2.sbisec.co.jp/ETGate/?_ControlID=WPLETpfR001Control&_PageID=DefaultPID&_DataStoreID=DSWPLETpfR001Control&_ActionID=DefaultAID&getFlg=on
          ('click',
           '//a[text()="登録銘柄リストの追加・置き換え"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy.do?
          ('click',
           '//*[@id="pfcopyinputForm"]/table/tbody/tr/td/div[3]/p/a'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/sender.do
          ('click',
           '//*[@name="tool_from" and @value="3"]'),
          ('click',
           '//input[@value="次へ"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/sendercheck.do
          ('click',
           '//*[@name="tool_to_1" and @value="1"]'),
          ('click',
           '//input[@value="次へ"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/receivercheck.do
          ('click',
           '//*[@name="add_replace_tool_01" and @value="1_2"]'),
          ('click',
           '//input[@value="確認画面へ"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/selectcheck.do
          ('click',
           '//input[@value="指示実行"]')]}

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
    for i in range(len(action)):
        command = action[i][0]
        arguments = action[i][1]
        if command == 'get':
            driver.get(arguments)
        elif command == 'click':
            driver.find_element(By.XPATH, arguments).click()
        elif command == 'sleep':
            time.sleep(int(arguments))

def convert_to_yahoo_finance(portfolio, csv_root):
    import csv
    import json

    with open(portfolio) as f:
        dictionary = json.load(f)

    if not os.path.isdir(csv_root):
        try:
            os.mkdir(csv_root)
        except OSError as e:
            print(e)
            sys.exit(1)

    watchlists = []
    HEADER = ['Symbol', 'Current Price', 'Date', 'Time', 'Change', 'Open',
              'High', 'Low', 'Volume', 'Trade Date', 'Purchase Price',
              'Quantity', 'Commission', 'High Limit', 'Low Limit', 'Comment']
    row = []
    for i in range(len(HEADER) - 1):
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

def export_to_yahoo_finance(driver, csv_root, watchlist):
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

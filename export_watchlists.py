import os
import sys

from selenium.webdriver.common.by import By

def main():
    import re

    import account
    import file_utilities

    config = configure()
    # with open(config.path, 'w', encoding='utf-8') as f:
    #     config.write(f)

    HYPERSBI2_ROOT = os.path.expandvars(r'%APPDATA%\SBI Securities\HYPERSBI2')
    identifier = ''
    # FIXME
    for f in os.listdir(HYPERSBI2_ROOT):
        if re.match('^[0-9a-z]{32}$', f):
            identifier = f

    if identifier:
        portfolio = os.path.join(HYPERSBI2_ROOT, identifier, 'portfolio.json')
    else:
        print('unspecified identifier')
        sys.exit(1)

    file_utilities.backup_file(portfolio,
                               os.path.join(
                                   os.path.expanduser('~'),
                                   r'Dropbox\Documents\Trading\Backups'))

    driver = account.login(account.configure('SBI Securities'))
    interact_with_browser(config, driver)
    driver.quit()

    convert_to_yahoo_finance(portfolio, os.path.join(os.path.expanduser('~'),
                                                     'Downloads'))

def configure():
    import configparser

    config = configparser.ConfigParser()
    config['SBI Securities'] = \
        {'replace_sbi_securities_with_hypersbi2':
         [('click_element',
           '//*[@id="link02M"]/ul/li[1]/a'),
          # https://site2.sbisec.co.jp/ETGate/?_ControlID=WPLETpfR001Control&_PageID=DefaultPID&_DataStoreID=DSWPLETpfR001Control&_ActionID=DefaultAID&getFlg=on
          ('click_element',
           '//a[text()="登録銘柄リストの追加・置き換え"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy.do?
          ('click_element',
           '//*[@id="pfcopyinputForm"]/table/tbody/tr/td/div[3]/p/a'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/sender.do
          ('click_element',
           '//*[@name="tool_from" and @value="3"]'),
          ('click_element',
           '//input[@value="次へ"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/sendercheck.do
          ('click_element',
           '//*[@name="tool_to_1" and @value="1"]'),
          ('click_element',
           '//input[@value="次へ"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/receivercheck.do
          ('click_element',
           '//*[@name="add_replace_tool_01" and @value="1_2"]'),
          ('click_element',
           '//input[@value="確認画面へ"]'),
          # https://site0.sbisec.co.jp/marble/portfolio/pfcopy/selectcheck.do
          ('click_element',
           '//input[@value="指示実行"]')]}
    config['Yahoo Finance'] = \
        {'export_hypersbi2_to_yahoo_finance':
         []}
    config.path = os.path.splitext(__file__)[0] + '.ini'
    config.read(config.path, encoding='utf-8')
    return config

def interact_with_browser(config, driver):
    commands = eval(config['SBI Securities']['replace_sbi_securities_with_hypersbi2'])
    for i in range(len(commands)):
        command = commands[i][0]
        arguments = commands[i][1]
        if command == 'click_element':
            driver.find_element(By.XPATH, arguments).click()

def convert_to_yahoo_finance(portfolio, output_root):
    import csv
    import json

    with open(portfolio) as f:
        dictionary = json.load(f)

    if not os.path.isdir(output_root):
        try:
            os.makedirs(output_root)
        except OSError as e:
            print(e)
            sys.exit(1)

    HEADER = ['Symbol', 'Current Price', 'Date', 'Time', 'Change', 'Open',
              'High', 'Low', 'Volume', 'Trade Date', 'Purchase Price',
              'Quantity', 'Commission', 'High Limit', 'Low Limit', 'Comment']
    row = []
    for i in range(len(HEADER) - 1):
        row.append('')

    for list_index in range(len(dictionary['list'])):
        list_name = dictionary['list'][list_index]['listName']
        csvfile = open(os.path.join(output_root, list_name + '.csv'), 'w')
        writer = csv.writer(csvfile)
        writer.writerow(HEADER)
        dictionary['list'][list_index]['secList'].reverse()
        for item in dictionary['list'][list_index]['secList']:
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

        csvfile.close()

if __name__ == '__main__':
    main()

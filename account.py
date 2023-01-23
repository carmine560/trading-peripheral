import os

def configure(service):
    import configparser

    import gnupg

    config = configparser.ConfigParser()
    config['Common'] = {'url': 'URL',
                        'user_id_xpath': 'USER_ID_XPATH',
                        'user_password_xpath': 'USER_PASSWORD_XPATH',
                        'login_xpath': 'LOGIN_XPATH'}
    config['Account'] = {'user_id': 'USER_ID',
                         'user_password': 'USER_PASSWORD'}
    config_home = os.path.join(os.path.expandvars('%LOCALAPPDATA%'),
                               os.path.splitext(os.path.basename(__file__))[0])
    config.path = os.path.join(config_home, service + '.ini.gpg')
    gpg = gnupg.GPG()
    if os.path.exists(config.path):
        with open(config.path, 'rb') as f:
            decrypted_data = gpg.decrypt_file(f)

        config.read_string(str(decrypted_data))
        return config
    else:
        import io
        import sys

        if not os.path.isdir(config_home):
            try:
                os.makedirs(config_home)
            except OSError as e:
                print(e)
                sys.exit(1)

        private_keys = gpg.list_keys(True)
        fingerprint = private_keys[0]['fingerprint']
        with io.StringIO() as s:
            config.write(s)
            s.seek(0)
            gpg.encrypt(s.read(), fingerprint, output=config.path)
            sys.exit()

def login(config):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.edge.options import Options
    from selenium.webdriver.edge.service import Service
    from webdriver_manager.microsoft import EdgeChromiumDriverManager

    service = Service(executable_path=EdgeChromiumDriverManager().install(),
                      log_path=os.path.devnull)
    options = Options()
    options.headless = True
    driver = webdriver.Edge(service=service, options=options)
    driver.get(config['Common']['url'])
    user_id_input = driver.find_element(By.XPATH,
                                        config['Common']['user_id_xpath'])
    user_id_input.send_keys(config['Account']['user_id'])
    user_password_input = \
        driver.find_element(By.XPATH, config['Common']['user_password_xpath'])
    user_password_input.send_keys(config['Account']['user_password'])
    driver.find_element(By.XPATH, config['Common']['login_xpath']).click()
    # FIXME
    driver.implicitly_wait(5)
    return driver

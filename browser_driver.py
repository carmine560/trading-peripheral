def initialize(user_data_dir=None, profile_directory=None):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    service = Service(executable_path=ChromeDriverManager().install())
    options = Options()
    # TODO
    options.add_argument('--headless=new')
    if user_data_dir and profile_directory:
        options.add_argument('--user-data-dir=' + user_data_dir)
        options.add_argument('--profile-directory=' + profile_directory)

    driver = webdriver.Chrome(service=service, options=options)
    # TODO
    driver.implicitly_wait(4)
    return driver

def execute_action(driver, action):
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
                execute_action(driver, action[index][2])
        elif command == 'get':
            driver.get(argument)
        elif command == 'refresh':
            driver.refresh()
        elif command == 'send_keys':
            driver.find_element(By.XPATH, argument).send_keys(action[index][2])
        elif command == 'sleep':
            time.sleep(int(argument))

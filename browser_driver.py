def initialize(headless=True, user_data_directory=None, profile_directory=None,
               implicitly_wait=2):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    service = Service(executable_path=ChromeDriverManager().install())
    options = Options()
    if headless:
        options.add_argument('--headless=new')
    if user_data_directory and profile_directory:
        options.add_argument('--user-data-dir=' + user_data_directory)
        options.add_argument('--profile-directory=' + profile_directory)

    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(implicitly_wait)
    return driver

def execute_action(driver, action, element=None, text=None):
    import time

    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    for index in range(len(action)):
        command = action[index][0]
        if len(action[index]) > 1:
            argument = action[index][1]
        if len(action[index]) > 2:
            additional_argument = action[index][2]

        if command == 'clear':
            driver.find_element(By.XPATH, argument).clear()
        elif command == 'click':
            driver.find_element(By.XPATH, argument).click()
        elif command == 'get':
            driver.get(argument)
        elif command == 'refresh':
            driver.refresh()
        elif command == 'send_keys':
            if additional_argument == 'enter':
                driver.find_element(By.XPATH, argument).send_keys(Keys.ENTER)
            elif additional_argument == 'element':
                driver.find_element(By.XPATH, argument).send_keys(element)
            else:
                driver.find_element(By.XPATH, argument).send_keys(
                    additional_argument)
        elif command == 'sleep':
            time.sleep(float(argument))
        elif command == 'text':
            text.append(driver.find_element(By.XPATH, argument).text)

        # Control Flow Commands
        elif command == 'exist':
            if driver.find_elements(By.XPATH, argument):
                execute_action(driver, additional_argument, element=element,
                               text=text)
            elif text is not None:
                # TODO
                import re

                match = re.search(r'//.*\[contains\(text\(\), "(.+)"\)\]',
                                  argument)
                if match:
                    text.append(f'{match.group(1)} does not exist.')
        elif command == 'for':
            for element in argument.split(', '):
                execute_action(driver, additional_argument, element=element,
                               text=text)
                time.sleep(1)

        else:
            print(command, 'is not a recognized command.')
            return False

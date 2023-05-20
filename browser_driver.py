def initialize(headless=True, user_data_directory=None, profile_directory=None,
               implicitly_wait=2):
    """Initialize a Selenium webdriver instance with Chrome browser.

    Args:
        headless (bool): Whether to run the browser in headless
        mode. Default is True.
        user_data_directory (str): Path to user data directory. Default
        is None.
        profile_directory (str): Path to profile directory. Default is
        None.
        implicitly_wait (int): Number of seconds to wait for the page to
        load. Default is 2.

    Returns:
        A webdriver instance of Chrome browser.

    Raises:
        WebDriverException: If the driver executable is not found."""
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

def execute_action(driver, action):
    """Execute a series of actions on a Selenium WebDriver.

    Args:
        driver: A Selenium WebDriver instance
        action: A list of actions to be executed on the WebDriver

    Returns:
        None

    Raises:
        None

    Notes:
        The action list is a list of tuples, where each tuple represents
        an action to be executed on the WebDriver. The first element of
        the tuple is the command to be executed, and the subsequent
        elements are the arguments for the command. The supported
        commands are:

        - clear: Clears the element specified by the XPATH argument
        - click: Clicks the element specified by the XPATH argument
        - get: Navigates the WebDriver to the URL specified by the
          argument
        - refresh: Refreshes the current page
        - send_keys: Sends the additional argument to the element
          specified by the XPATH argument
        - sleep: Pauses the execution for the number of seconds
          specified by the argument
        - exist: Checks if the element specified by the XPATH argument
          exists. If it does, executes the additional argument as a new
          action list."""
    import time

    from selenium.webdriver.common.by import By

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
            driver.find_element(By.XPATH, argument).send_keys(
                additional_argument)
        elif command == 'sleep':
            time.sleep(float(argument))

        # Boolean Command
        elif command == 'exist':
            if driver.find_elements(By.XPATH, argument):
                execute_action(driver, additional_argument)

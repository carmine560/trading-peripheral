from selenium.webdriver.common.keys import Keys

from core_utilities.errors import BrowserAutomationError
from web_utilities import browser_driver


class FakeElement:
    def __init__(self, text=""):
        self.text = text
        self.cleared = False
        self.clicked = False
        self.sent_keys = []
        self.visible = True
        self.enabled = True

    def clear(self):
        self.cleared = True

    def click(self):
        self.clicked = True

    def send_keys(self, value):
        self.sent_keys.append(value)

    def is_displayed(self):
        return self.visible

    def is_enabled(self):
        return self.enabled


class FakeDriver:
    def __init__(self):
        self.visited = []
        self.refreshed = 0
        self.scripts = []
        self._trading_peripheral_wait_timeout = 0.1
        self.current_url = "https://example.com/page"
        self.title = "Example"
        self.elements = {
            "//input": FakeElement(),
            "//button": FakeElement(),
            "//message": FakeElement(text="ready"),
        }
        self.existing = {"//present"}

    def get(self, url):
        self.visited.append(url)

    def refresh(self):
        self.refreshed += 1

    def execute_script(self, script, element):
        self.scripts.append((script, element))

    def find_element(self, by, xpath):
        return self.elements[xpath]

    def find_elements(self, by, xpath):
        if xpath in self.elements:
            return [self.elements[xpath]]
        if xpath in self.existing:
            return [FakeElement()]
        return []


def test_execute_action_runs_supported_commands():
    driver = FakeDriver()
    text = []
    action = [
        ("get", "https://example.com"),
        ("send_keys", "//input", "value"),
        ("send_keys", "//input", "enter"),
        ("click", "//button"),
        ("text", "//message"),
    ]

    result = browser_driver.execute_action(driver, action, text=text)

    assert result is True
    assert driver.visited == ["https://example.com"]
    assert driver.elements["//input"].sent_keys == ["value", Keys.ENTER]
    assert driver.elements["//button"].clicked is True
    assert driver.scripts == [
        (
            "arguments[0].scrollIntoView({block: 'center'});",
            driver.elements["//button"],
        )
    ]
    assert text == ["ready"]


def test_execute_action_handles_control_flow():
    driver = FakeDriver()
    text = []
    action = [
        ("exist", "//present", [("click", "//button")]),
        ("for", "A, B", [("send_keys", "//input", "element")]),
        ("exist", '//div[contains(text(), "Missing")]', []),
    ]

    result = browser_driver.execute_action(driver, action, text=text)

    assert result is True
    assert driver.elements["//button"].clicked is True
    assert driver.elements["//input"].sent_keys == ["A", "B"]
    assert text == ["Missing does not exist."]


def test_execute_action_evaluates_string_actions():
    driver = FakeDriver()

    result = browser_driver.execute_action(
        driver,
        "[('send_keys', '//input', 'element')]",
        element="Ticker",
    )

    assert result is True
    assert driver.elements["//input"].sent_keys == ["Ticker"]


def test_execute_action_rejects_unknown_commands(capsys):
    driver = FakeDriver()

    try:
        browser_driver.execute_action(driver, [("unknown", "value")])
    except BrowserAutomationError as e:
        message = str(e)
    else:
        raise AssertionError("Expected BrowserAutomationError")

    captured = capsys.readouterr()
    assert message == "Unrecognized browser command: 'unknown'"
    assert captured.out == ""


def test_execute_action_logs_failing_instruction(capsys, monkeypatch):
    driver = FakeDriver()

    monkeypatch.setattr(
        browser_driver,
        "_wait_for_clickable",
        lambda current_driver, xpath: (_ for _ in ()).throw(
            RuntimeError(f"blocked: {xpath}")
        ),
    )

    try:
        browser_driver.execute_action(driver, [("click", "//button")])
    except BrowserAutomationError as e:
        assert str(e) == "Browser instruction failed: ('click', '//button')"
        assert isinstance(e.__cause__, RuntimeError)
        assert str(e.__cause__) == "blocked: //button"
    else:
        raise AssertionError("Expected BrowserAutomationError")

    captured = capsys.readouterr()
    assert captured.out == ""


def test_wait_for_clickable_skips_hidden_duplicate_elements():
    driver = FakeDriver()
    hidden = FakeElement()
    hidden.visible = False
    visible = FakeElement()

    driver.find_elements = lambda by, xpath: [hidden, visible]

    result = browser_driver._wait_for_clickable(driver, "//duplicate")

    assert result is visible


def test_wait_for_clickable_reports_timeout_context(monkeypatch):
    driver = FakeDriver()
    hidden = FakeElement()
    hidden.visible = False
    driver.find_elements = lambda by, xpath: [hidden]
    driver._trading_peripheral_wait_timeout = 0.01

    try:
        browser_driver._wait_for_clickable(driver, "//duplicate")
    except Exception as e:
        message = str(e)
    else:
        raise AssertionError("Expected timeout")

    assert "No interactable match for XPath '//duplicate'" in message
    assert "matches=1" in message
    assert "url='https://example.com/page'" in message
    assert "title='Example'" in message


def test_initialize_requests_desktop_window_and_maximizes(monkeypatch):
    recorded_arguments = []

    class FakeOptions:
        def add_argument(self, argument):
            recorded_arguments.append(argument)

    class FakeChromeDriver:
        def __init__(self, options):
            self.options = options
            self.maximized = False
            self.implicit_wait_value = None

        def maximize_window(self):
            self.maximized = True

        def implicitly_wait(self, value):
            self.implicit_wait_value = value

        def execute_cdp_cmd(self, command, payload):
            self.cdp_command = (command, payload)

        def execute_script(self, script):
            return "HeadlessChrome"

    driver_holder = {}

    monkeypatch.setattr(browser_driver, "Options", FakeOptions)
    monkeypatch.setattr(
        browser_driver.webdriver,
        "Chrome",
        lambda options: driver_holder.setdefault(
            "driver", FakeChromeDriver(options)
        ),
    )

    driver = browser_driver.initialize(
        headless=False,
        user_data_directory="C:/Chrome/Selenium",
        profile_directory="Default",
        implicitly_wait=4,
    )

    assert "--window-size=1600,1000" in recorded_arguments
    assert "--user-data-dir=C:/Chrome/Selenium" in recorded_arguments
    assert "--profile-directory=Default" in recorded_arguments
    assert "--restore-last-session=false" in recorded_arguments
    assert driver.maximized is True
    assert driver.implicit_wait_value == 4
    assert driver._trading_peripheral_wait_timeout == 4.0

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


def test_execute_action_passes_explicit_wait_timeout(monkeypatch):
    driver = FakeDriver()
    wait_calls = []

    monkeypatch.setattr(
        browser_driver,
        "_wait_for_visible",
        lambda current_driver, xpath, wait_timeout: wait_calls.append(
            (current_driver, xpath, wait_timeout)
        )
        or driver.elements[xpath],
    )

    browser_driver.execute_action(
        driver,
        [("send_keys", "//input", "value")],
        wait_timeout=3.5,
    )

    assert wait_calls == [(driver, "//input", 3.5)]


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
        lambda current_driver, xpath, wait_timeout: (_ for _ in ()).throw(
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

    result = browser_driver._wait_for_clickable(driver, "//duplicate", 0.1)

    assert result is visible


def test_wait_for_clickable_reports_timeout_context(monkeypatch):
    driver = FakeDriver()
    hidden = FakeElement()
    hidden.visible = False
    driver.find_elements = lambda by, xpath: [hidden]

    try:
        browser_driver._wait_for_clickable(driver, "//duplicate", 0.01)
    except Exception as e:
        message = str(e)
    else:
        raise AssertionError("Expected timeout")

    assert "No interactable match for XPath '//duplicate'" in message
    assert "matches=1" in message
    assert "url='https://example.com/page'" in message
    assert "title='Example'" in message


def test_initialize_configures_firefox_profile(monkeypatch):
    class FakeOptions:
        def __init__(self):
            self.profile = None

    class FakeFirefoxDriver:
        def __init__(self, options):
            self.options = options

    driver_holder = {}

    monkeypatch.setattr(browser_driver, "Options", FakeOptions)
    monkeypatch.setattr(
        browser_driver.webdriver,
        "Firefox",
        lambda options: driver_holder.setdefault(
            "driver", FakeFirefoxDriver(options)
        ),
    )

    driver = browser_driver.initialize(
        firefox_profile_directory="C:/Firefox/Selenium"
    )

    assert driver.options.profile == "C:/Firefox/Selenium"


def test_initialize_leaves_profile_unset_by_default(monkeypatch):
    class FakeOptions:
        def __init__(self):
            self.profile = None

    class FakeFirefoxDriver:
        def __init__(self, options):
            self.options = options

    driver_holder = {}

    monkeypatch.setattr(browser_driver, "Options", FakeOptions)
    monkeypatch.setattr(
        browser_driver.webdriver,
        "Firefox",
        lambda options: driver_holder.setdefault(
            "driver", FakeFirefoxDriver(options)
        ),
    )

    driver = browser_driver.initialize()

    assert driver.options.profile is None

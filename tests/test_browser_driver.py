from selenium.webdriver.common.keys import Keys

from web_utilities import browser_driver


class FakeElement:
    def __init__(self, text=""):
        self.text = text
        self.cleared = False
        self.clicked = False
        self.sent_keys = []

    def clear(self):
        self.cleared = True

    def click(self):
        self.clicked = True

    def send_keys(self, value):
        self.sent_keys.append(value)


class FakeDriver:
    def __init__(self):
        self.visited = []
        self.refreshed = 0
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

    def find_element(self, by, xpath):
        return self.elements[xpath]

    def find_elements(self, by, xpath):
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

    result = browser_driver.execute_action(driver, [("unknown", "value")])

    captured = capsys.readouterr()
    assert result is False
    assert "'unknown' is not a recognized command." in captured.out

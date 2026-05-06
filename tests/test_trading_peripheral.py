from configparser import ConfigParser
from types import SimpleNamespace

import trading_peripheral


class _FakeTrade:
    vendor = "SBI Securities"
    process = "HYPERSBI2"
    actions_section = "HYPERSBI2 Actions"


class _FakeDriver:
    def __init__(self):
        self.quit_calls = 0

    def quit(self):
        self.quit_calls += 1


def test_run_browser_actions_retries_after_initialize_failure(monkeypatch):
    args = SimpleNamespace(s=True, S=False, o=False)
    trade = _FakeTrade()
    config = ConfigParser(interpolation=None)
    config["General"] = {
        "headless": "True",
        "user_data_directory": "",
        "profile_directory": "Default",
        "implicitly_wait": "4",
    }
    config[trade.actions_section] = {
        "replace_SBI Securities_watchlists": "[]",
    }

    init_calls = []
    driver = _FakeDriver()

    def fake_initialize(**kwargs):
        init_calls.append(kwargs)
        if len(init_calls) == 1:
            raise RuntimeError("Chrome failed to start")
        return driver

    actions = []
    sleep_calls = []

    monkeypatch.setattr(
        trading_peripheral.browser_driver,
        "initialize",
        fake_initialize,
    )
    monkeypatch.setattr(
        trading_peripheral.browser_driver,
        "execute_action",
        lambda current_driver, action: actions.append(
            (current_driver, action)
        ),
    )
    monkeypatch.setattr(
        trading_peripheral.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    trading_peripheral._run_browser_actions(args, trade, config)

    assert len(init_calls) == 2
    assert sleep_calls == [10]
    assert actions == [(driver, "[]")]
    assert driver.quit_calls == 1

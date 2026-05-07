from configparser import ConfigParser
from types import SimpleNamespace

import trading_peripheral
from core_utilities.errors import ConfigBuildError, ExternalServiceError


class _FakeTrade:
    vendor = "SBI Securities"
    process = "HYPERSBI2"
    actions_section = "HYPERSBI2 Actions"


class _FakeDriver:
    def __init__(self):
        self.quit_calls = 0

    def quit(self):
        self.quit_calls += 1


class _FakeMaintenanceTrade:
    config_directory = "/tmp"
    config_path = "/tmp/trading_peripheral.ini"
    maintenance_schedules_section = "SBI Securities Maintenance Schedules"


class _FakeMatched:
    encoding = "utf-8"


class _FakeRoot:
    def xpath(self, expression):
        return []


class _FakeResponse:
    def __init__(self):
        self.content = b"<title>Maintenance</title>"
        self.text = "<title>Maintenance</title>"
        self.encoding = None

    def raise_for_status(self):
        return None


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


def test_configure_raises_when_application_data_directory_missing(
    monkeypatch,
):
    trade = SimpleNamespace(
        vendor="SBI Securities",
        process="HYPERSBI2",
        config_path="/tmp/trading_peripheral.ini",
        investment_tools_news_section="SBI Securities Investment Tools News",
        maintenance_schedules_section="SBI Securities Maintenance Schedules",
        order_status_section="SBI Securities Order Status",
        brokerage_variables_section="SBI Securities Variables",
        release_notes_section="HYPERSBI2 Release Notes",
        actions_section="HYPERSBI2 Actions",
    )

    monkeypatch.setattr(
        trading_peripheral.os.path,
        "expandvars",
        lambda value: "/tmp/appdata",
    )
    monkeypatch.setattr(
        trading_peripheral.os.path,
        "isdir",
        lambda path: False,
    )

    try:
        trading_peripheral.configure(
            trade, can_interpolate=False, can_override=False
        )
    except ConfigBuildError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ConfigBuildError")

    assert message == (
        "Application data directory does not exist: "
        "/tmp/appdata\\SBI Securities\\HYPERSBI2"
    )


def _build_maintenance_config():
    config = ConfigParser(interpolation=None)
    config["SBI Securities Maintenance Schedules"] = {
        "url": "https://example.com/maintenance",
        "timezone": "Asia/Tokyo",
        "last_inserted": "",
        "calendar_id": "",
        "all_service_xpath": "//all-service",
        "all_service_name": "all",
        "services": "()",
        "service_xpath": "//service",
        "function_xpath": "following::p[1]",
        "datetime_xpath": "ancestor::li[1]/div[1]",
        "range_splitter_regex": "〜|～",
        "datetime_regex": (
            r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日（[^）]+）(\d{1,2}:\d{2})$"
        ),
        "year_group": "1",
        "month_group": "2",
        "day_group": "3",
        "time_group": "4",
        "previous_bodies": "{}",
    }
    return config


def test_insert_maintenance_schedules_falls_back_without_last_modified(
    monkeypatch,
):
    trade = _FakeMaintenanceTrade()
    config = _build_maintenance_config()
    response = _FakeResponse()
    calendar_calls = []
    write_calls = []

    monkeypatch.setattr(
        trading_peripheral.web_utilities,
        "make_head_request",
        lambda url: SimpleNamespace(headers={}),
    )
    monkeypatch.setattr(
        trading_peripheral.requests,
        "get",
        lambda url, timeout: response,
    )
    monkeypatch.setattr(
        trading_peripheral,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        trading_peripheral.html,
        "fromstring",
        lambda text: _FakeRoot(),
    )
    monkeypatch.setattr(
        trading_peripheral.google_services,
        "get_calendar_resource",
        lambda *args: calendar_calls.append(args) or ("resource", "calendar"),
    )
    monkeypatch.setattr(
        trading_peripheral.configuration,
        "write_config",
        lambda *args, **kwargs: write_calls.append((args, kwargs)),
    )

    trading_peripheral.insert_maintenance_schedules(trade, config)

    assert response.encoding == "utf-8"
    assert calendar_calls
    assert write_calls
    assert config[trade.maintenance_schedules_section]["calendar_id"] == (
        "calendar"
    )
    assert config[trade.maintenance_schedules_section]["last_inserted"]


def test_insert_maintenance_schedules_recovers_from_head_failure(
    monkeypatch,
):
    trade = _FakeMaintenanceTrade()
    config = _build_maintenance_config()
    response = _FakeResponse()
    calendar_calls = []

    monkeypatch.setattr(
        trading_peripheral.web_utilities,
        "make_head_request",
        lambda url: (_ for _ in ()).throw(
            ExternalServiceError("HEAD request failed")
        ),
    )
    monkeypatch.setattr(
        trading_peripheral.requests,
        "get",
        lambda url, timeout: response,
    )
    monkeypatch.setattr(
        trading_peripheral,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        trading_peripheral.html,
        "fromstring",
        lambda text: _FakeRoot(),
    )
    monkeypatch.setattr(
        trading_peripheral.google_services,
        "get_calendar_resource",
        lambda *args: calendar_calls.append(args) or ("resource", "calendar"),
    )
    monkeypatch.setattr(
        trading_peripheral.configuration,
        "write_config",
        lambda *args, **kwargs: None,
    )

    trading_peripheral.insert_maintenance_schedules(trade, config)

    assert response.encoding == "utf-8"
    assert calendar_calls


def test_check_web_page_send_email_message_raises_on_get_failure(
    monkeypatch,
):
    trade = SimpleNamespace(
        config_directory="/tmp",
        config_path="/tmp/trading_peripheral.ini",
    )
    section = "SBI Securities Investment Tools News"
    config = ConfigParser(interpolation=None)
    config[section] = {
        "url": "https://example.com/news",
        "latest_news_xpath": "//latest",
        "latest_news_text": "",
    }

    monkeypatch.setattr(
        trading_peripheral.requests,
        "get",
        lambda url, timeout: (_ for _ in ()).throw(
            trading_peripheral.requests.exceptions.HTTPError("403")
        ),
    )

    try:
        trading_peripheral.check_web_page_send_email_message(
            trade, config, section
        )
    except ExternalServiceError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert "GET request failed for https://example.com/news" in message


def test_insert_maintenance_schedules_raises_on_get_failure(monkeypatch):
    trade = _FakeMaintenanceTrade()
    config = _build_maintenance_config()

    monkeypatch.setattr(
        trading_peripheral.web_utilities,
        "make_head_request",
        lambda url: SimpleNamespace(headers={}),
    )
    monkeypatch.setattr(
        trading_peripheral.requests,
        "get",
        lambda url, timeout: (_ for _ in ()).throw(
            trading_peripheral.requests.exceptions.HTTPError("500")
        ),
    )

    try:
        trading_peripheral.insert_maintenance_schedules(trade, config)
    except ExternalServiceError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert "GET request failed for https://example.com/maintenance" in message

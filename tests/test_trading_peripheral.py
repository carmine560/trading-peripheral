from configparser import ConfigParser
from types import SimpleNamespace

from app import config as app_config
from app import maintenance as app_maintenance
from app import monitoring as app_monitoring
from app import order_status as app_order_status
import trading_peripheral
from core_utilities.errors import (
    ConfigBuildError,
    ExternalServiceError,
    MarketDataError,
    ProcessStateError,
    ScraperError,
)


class _FakeTrade:
    vendor = "SBI Securities"
    process = "HYPERSBI2"
    actions_section = "HYPERSBI2 Actions"


class _FakeDriver:
    def __init__(self):
        self.quit_calls = 0
        self.page_source = "<html></html>"

    def quit(self):
        self.quit_calls += 1


class _FakeMaintenanceTrade:
    config_directory = "/tmp"
    config_path = "/tmp/trading_peripheral.ini"
    maintenance_schedules_section = "SBI Securities Maintenance Schedules"


class _FakeMatched:
    encoding = "utf-8"


class _FakeElement:
    def __init__(self, text=""):
        self._text = text

    def text_content(self):
        return self._text

    def xpath(self, expression):
        if expression == "normalize-space(.)":
            return self._text
        return []


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


def test_configure_skips_watchlist_discovery_when_directory_missing(
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
        instruction_items={},
    )

    monkeypatch.setattr(
        app_config.os.path,
        "expandvars",
        lambda value: "/tmp/appdata",
    )
    monkeypatch.setattr(
        app_config.os.path,
        "isdir",
        lambda path: False,
    )

    config = trading_peripheral.configure(
        trade, can_interpolate=False, can_override=False
    )
    assert config[trade.process]["watchlists"] == ""


def test_ensure_watchlists_path_raises_when_directory_missing(monkeypatch):
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
        instruction_items={},
    )

    monkeypatch.setattr(
        app_config.os.path,
        "expandvars",
        lambda value: "/tmp/appdata",
    )
    monkeypatch.setattr(app_config.os.path, "isdir", lambda path: False)

    config = trading_peripheral.configure(
        trade, can_interpolate=False, can_override=False
    )

    try:
        app_config.ensure_watchlists_path(config, trade)
    except ConfigBuildError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ConfigBuildError")

    assert message == (
        "Application data directory does not exist: "
        "/tmp/appdata\\SBI Securities\\HYPERSBI2"
    )


def test_ensure_watchlists_path_raises_when_identifier_missing(monkeypatch):
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
        instruction_items={},
    )

    monkeypatch.setattr(
        app_config.os.path,
        "expandvars",
        lambda value: "/tmp/appdata",
    )
    monkeypatch.setattr(app_config.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(app_config.os, "listdir", lambda path: ["notes"])

    config = trading_peripheral.configure(
        trade, can_interpolate=False, can_override=False
    )

    try:
        app_config.ensure_watchlists_path(config, trade)
    except ConfigBuildError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ConfigBuildError")

    assert message == "Unable to determine the latest watchlist identifier."


def test_manage_snapshots_raises_process_state_error(monkeypatch):
    args = SimpleNamespace(d=True, D=False)
    trade = SimpleNamespace(process="HYPERSBI2")
    config = ConfigParser(interpolation=None)
    config["HYPERSBI2"] = {
        "application_data_directory": "/tmp/HYPERSBI2",
        "snapshot_directory": "/tmp",
    }
    config["General"] = {"fingerprint": ""}

    monkeypatch.setattr(
        trading_peripheral.process_utilities,
        "is_running",
        lambda process: True,
    )

    try:
        trading_peripheral._manage_snapshots(args, trade, config)
    except ProcessStateError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ProcessStateError")

    assert message == "'HYPERSBI2' is running."


def test_order_status_raises_market_data_error_on_parse_failure(monkeypatch):
    trade = SimpleNamespace(order_status_section="SBI Securities Order Status")
    config = ConfigParser(interpolation=None)
    config[trade.order_status_section] = {
        "table_identifier": "注文種別",
    }
    driver = _FakeDriver()

    monkeypatch.setattr(
        app_order_status.pd,
        "read_html",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad html")),
    )

    try:
        app_order_status.extract_sbi_securities_order_status(
            trade, config, driver
        )
    except MarketDataError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected MarketDataError")

    assert message == (
        "Unable to parse the order status table from the current page."
    )


def test_main_returns_error_code_for_trading_errors(monkeypatch, capsys):
    def raise_error():
        raise ProcessStateError("'HYPERSBI2' is running.")

    monkeypatch.setattr(trading_peripheral, "run", raise_error)

    assert trading_peripheral.main() == 1
    assert capsys.readouterr().out == "'HYPERSBI2' is running.\n"


def test_main_returns_error_code_for_config_errors(monkeypatch, capsys):
    def raise_error():
        raise trading_peripheral.configuration.ConfigError("missing section")

    monkeypatch.setattr(trading_peripheral, "run", raise_error)

    assert trading_peripheral.main() == 1
    assert capsys.readouterr().out == "Configuration error: missing section\n"


def test_monitoring_raises_scraper_error_for_missing_news_node(
    monkeypatch,
):
    trade = SimpleNamespace(config_directory="/tmp", config_path="/tmp/config")
    config = ConfigParser(interpolation=None)
    config["General"] = {
        "email_message_from": "from@example.com",
        "email_message_to": "to@example.com",
    }
    config["News"] = {
        "url": "https://example.com/news",
        "latest_news_xpath": "//headline",
        "latest_news_text": "",
    }
    response = _FakeResponse()

    monkeypatch.setattr(
        app_monitoring.requests,
        "get",
        lambda url, timeout: response,
    )
    monkeypatch.setattr(
        app_monitoring,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        app_monitoring.html,
        "fromstring",
        lambda text: _FakeRoot(),
    )

    try:
        app_monitoring.check_web_page_send_email_message(trade, config, "News")
    except ScraperError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ScraperError")

    assert message == (
        "News latest news XPath matched 0 nodes for "
        "https://example.com/news: //headline"
    )


def test_monitoring_raises_scraper_error_for_duplicate_news_nodes(
    monkeypatch,
):
    trade = SimpleNamespace(config_directory="/tmp", config_path="/tmp/config")
    config = ConfigParser(interpolation=None)
    config["General"] = {
        "email_message_from": "from@example.com",
        "email_message_to": "to@example.com",
    }
    config["News"] = {
        "url": "https://example.com/news",
        "latest_news_xpath": "//headline",
        "latest_news_text": "",
    }
    response = _FakeResponse()

    class _DuplicateRoot:
        def xpath(self, expression):
            return [_FakeElement("first"), _FakeElement("second")]

    monkeypatch.setattr(
        app_monitoring.requests,
        "get",
        lambda url, timeout: response,
    )
    monkeypatch.setattr(
        app_monitoring,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        app_monitoring.html,
        "fromstring",
        lambda text: _DuplicateRoot(),
    )

    try:
        app_monitoring.check_web_page_send_email_message(trade, config, "News")
    except ScraperError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ScraperError")

    assert message == (
        "News latest news XPath matched 2 nodes for "
        "https://example.com/news: //headline"
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
            r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日" r"（[^）]+）(\d{1,2}:\d{2})$"
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
        app_maintenance.web_utilities,
        "make_head_request",
        lambda url: SimpleNamespace(headers={}),
    )
    monkeypatch.setattr(
        app_maintenance.requests,
        "get",
        lambda url, timeout: response,
    )
    monkeypatch.setattr(
        app_maintenance,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        app_maintenance.html,
        "fromstring",
        lambda text: _FakeRoot(),
    )
    monkeypatch.setattr(
        app_maintenance.google_services,
        "get_calendar_resource",
        lambda *args: calendar_calls.append(args) or ("resource", "calendar"),
    )
    monkeypatch.setattr(
        app_maintenance.configuration,
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
        app_maintenance.web_utilities,
        "make_head_request",
        lambda url: (_ for _ in ()).throw(
            ExternalServiceError("HEAD request failed")
        ),
    )
    monkeypatch.setattr(
        app_maintenance.requests,
        "get",
        lambda url, timeout: response,
    )
    monkeypatch.setattr(
        app_maintenance,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        app_maintenance.html,
        "fromstring",
        lambda text: _FakeRoot(),
    )
    monkeypatch.setattr(
        app_maintenance.google_services,
        "get_calendar_resource",
        lambda *args: calendar_calls.append(args) or ("resource", "calendar"),
    )
    monkeypatch.setattr(
        app_maintenance.configuration,
        "write_config",
        lambda *args, **kwargs: None,
    )

    trading_peripheral.insert_maintenance_schedules(trade, config)

    assert response.encoding == "utf-8"


def test_insert_maintenance_schedules_raises_for_missing_function_node(
    monkeypatch,
):
    trade = _FakeMaintenanceTrade()
    config = _build_maintenance_config()
    config[trade.maintenance_schedules_section]["services"] = "('all',)"
    response = _FakeResponse()

    class _FakeSchedule:
        def xpath(self, expression):
            if (
                expression
                == config[trade.maintenance_schedules_section][
                    "function_xpath"
                ]
            ):
                return []
            if (
                expression
                == config[trade.maintenance_schedules_section][
                    "datetime_xpath"
                ]
            ):
                return [_FakeElement("03/14 09:00～10:00")]
            return []

    class _MaintenanceRoot:
        def xpath(self, expression):
            if (
                expression
                == config[trade.maintenance_schedules_section][
                    "all_service_xpath"
                ]
            ):
                return []
            if expression == (
                config[trade.maintenance_schedules_section][
                    "service_xpath"
                ].format("all")
            ):
                return [_FakeSchedule()]
            return []

    monkeypatch.setattr(
        app_maintenance.web_utilities,
        "make_head_request",
        lambda url: SimpleNamespace(headers={}),
    )
    monkeypatch.setattr(
        app_maintenance.requests,
        "get",
        lambda url, timeout: response,
    )
    monkeypatch.setattr(
        app_maintenance,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        app_maintenance.html,
        "fromstring",
        lambda text: _MaintenanceRoot(),
    )
    monkeypatch.setattr(
        app_maintenance.google_services,
        "get_calendar_resource",
        lambda *args: ("resource", "calendar"),
    )

    try:
        trading_peripheral.insert_maintenance_schedules(trade, config)
    except ScraperError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ScraperError")

    assert message == (
        "all maintenance function XPath matched 0 nodes for "
        "https://example.com/maintenance: following::p[1]"
    )

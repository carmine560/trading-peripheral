from configparser import ConfigParser
from types import SimpleNamespace

from app import cli as app_cli
from app import config as app_config
from app import maintenance as app_maintenance
from app import monitoring as app_monitoring
from app import order_status as app_order_status
from core_utilities.config_common import ConfigError
from core_utilities.errors import (
    ConfigBuildError,
    ExternalServiceError,
    MarketDataError,
    ProcessStateError,
    ScraperError,
)
import trading_peripheral


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


def test_get_arguments_rejects_snapshot_backup_and_restore(monkeypatch):
    monkeypatch.setattr(
        app_cli.sys, "argv", ["trading_peripheral.py", "-d", "-D"]
    )

    try:
        app_cli.get_arguments()
    except SystemExit as e:
        code = e.code
    else:
        raise AssertionError("Expected SystemExit")

    assert code == 2


def test_run_returns_after_launcher_generation(monkeypatch):
    args = SimpleNamespace(P=("SBI Securities", "HYPERSBI2"), BS=True)
    calls = []

    class FakeTrade:
        def __init__(self, vendor, process):
            calls.append(("trade", vendor, process))

    def fail_after_launcher(*args, **kwargs):
        raise AssertionError("run continued after launcher generation")

    monkeypatch.setattr(trading_peripheral, "get_arguments", lambda: args)
    monkeypatch.setattr(trading_peripheral, "Trade", FakeTrade)
    monkeypatch.setattr(
        trading_peripheral.file_utilities,
        "create_launchers_exit",
        lambda current_args, script_path: calls.append(
            ("launcher", current_args, script_path)
        )
        or True,
    )
    monkeypatch.setattr(
        trading_peripheral, "configure_exit", fail_after_launcher
    )
    monkeypatch.setattr(trading_peripheral, "configure", fail_after_launcher)

    trading_peripheral.run()

    assert calls[0] == ("trade", "SBI Securities", "HYPERSBI2")
    assert calls[1][0] == "launcher"
    assert calls[1][1] is args
    assert calls[1][2] == trading_peripheral.__file__


def test_trade_action_command_completions_match_browser_dispatch():
    trade = trading_peripheral.Trade("SBI Securities", "HYPERSBI2")

    assert trade.instruction_items["all_keys"] == list(
        trading_peripheral.browser_driver._COMMAND_DISPATCH
    )


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
    except ConfigBuildError as e:
        message = str(e)
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
    except ConfigBuildError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ConfigBuildError")

    assert message == "Unable to determine the latest watchlist identifier."


def test_configure_uses_single_release_note_match_xpath(monkeypatch):
    trade = SimpleNamespace(
        vendor="SBI Securities",
        process="HYPERSBI2",
        config_path="/tmp/trading_peripheral.ini",
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

    config = trading_peripheral.configure(
        trade, can_interpolate=False, can_override=False
    )

    assert config[trade.release_notes_section]["latest_news_xpath"] == (
        '(//p[contains(@class, "Rnote__ver")])[1]'
    )


def test_configure_matches_all_service_label_with_descendant_text(
    monkeypatch,
):
    trade = SimpleNamespace(
        vendor="SBI Securities",
        process="HYPERSBI2",
        config_path="/tmp/trading_peripheral.ini",
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

    config = trading_peripheral.configure(
        trade, can_interpolate=False, can_override=False
    )
    section = config[trade.maintenance_schedules_section]
    root = app_maintenance.html.fromstring(
        '<span class="marker-white font-xs font-bold">'
        '<font size="2">すべてのサービス</font>'
        "</span>"
    )

    assert "all_service_xpath" not in section
    assert "all_service_name" not in section
    matches = root.xpath(section["service_xpath"].format("すべてのサービス"))

    assert len(matches) == 1


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
    except ProcessStateError as e:
        message = str(e)
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
    except MarketDataError as e:
        message = str(e)
    else:
        raise AssertionError("Expected MarketDataError")

    assert message == (
        "Unable to parse the order status table from the current page."
    )


def _build_order_status_trade_config(monkeypatch):
    trade = SimpleNamespace(
        vendor="SBI Securities",
        process="HYPERSBI2",
        config_path="/tmp/trading_peripheral.ini",
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
    config = app_config.configure(trade, can_override=False)
    return trade, config


def _assert_order_status_market_data_error(monkeypatch, trade, config, df):
    driver = _FakeDriver()
    monkeypatch.setattr(
        app_order_status.pd,
        "read_html",
        lambda *args, **kwargs: [df],
    )

    try:
        app_order_status.extract_sbi_securities_order_status(
            trade, config, driver
        )
    except MarketDataError as e:
        message = str(e)
    else:
        raise AssertionError("Expected MarketDataError")

    assert message == "Unable to extract order status from the parsed table."


def test_order_status_extracts_default_columns_and_weighted_prices(
    monkeypatch,
):
    trade, config = _build_order_status_trade_config(monkeypatch)
    driver = _FakeDriver()
    captured = {}
    df = app_order_status.pd.DataFrame(
        [
            ["", "取消完了", "", None, "", "", "", ""],
            [
                "",
                "",
                "",
                "逆指値：現在値が1000円以下",
                "",
                "",
                "",
                "",
            ],
            ["", "", "逆指値注文", "ABC 1234 東証", "", "", "", ""],
            ["", "", "", "信新買", "", "", "100", "成行"],
            ["", "", "", "約定", "", "03/14 09:00:00", "40", "100"],
            ["", "", "", "約定", "", "03/14 09:01:00", "60", "102"],
            ["", "", "", "ABC 1234 東証", "", "", "", ""],
            ["", "", "", "信返売", "", "", "100", "指値"],
            ["", "", "", "約定", "", "03/14 10:30:00", "25", "110"],
            ["", "", "", "約定", "", "03/14 10:31:00", "75", "112"],
        ]
    )

    monkeypatch.setattr(
        app_order_status.pd,
        "read_html",
        lambda *args, **kwargs: [df],
    )

    def fake_to_clipboard(self, **kwargs):
        captured["rows"] = (
            self.astype(object).where(self.notna(), None).values.tolist()
        )
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        app_order_status.pd.DataFrame,
        "to_clipboard",
        fake_to_clipboard,
    )

    app_order_status.extract_sbi_securities_order_status(trade, config, driver)

    assert captured["rows"] == [
        [
            "03/14",
            "09:00:00",
            "1234",
            "100",
            "long stop market order",
            "101.2",
            "10:30:00",
            "111.5",
        ],
        [None, None, None, None, None, None, None, None],
    ]
    assert captured["kwargs"] == {
        "sep": ",",
        "header": False,
        "index": False,
        "quoting": 1,
    }


def test_order_status_raises_market_data_error_for_missing_column(
    monkeypatch,
):
    trade, config = _build_order_status_trade_config(monkeypatch)
    df = app_order_status.pd.DataFrame(
        [
            ["", "", "逆指値注文", "ABC 1234 東証", "", "", ""],
            ["", "", "", "信新買", "", "", "100"],
            ["", "", "", "約定", "", "03/14 09:00:00", "40"],
        ]
    )

    _assert_order_status_market_data_error(monkeypatch, trade, config, df)


def test_order_status_raises_market_data_error_for_short_row_block(
    monkeypatch,
):
    trade, config = _build_order_status_trade_config(monkeypatch)
    df = app_order_status.pd.DataFrame(
        [
            ["", "", "逆指値注文", "ABC 1234 東証", "", "", "", ""],
            ["", "", "", "信新買", "", "", "100", "成行"],
        ]
    )

    _assert_order_status_market_data_error(monkeypatch, trade, config, df)


def test_order_status_raises_market_data_error_for_bad_weighted_price(
    monkeypatch,
):
    trade, config = _build_order_status_trade_config(monkeypatch)
    df = app_order_status.pd.DataFrame(
        [
            ["", "", "逆指値注文", "ABC 1234 東証", "", "", "", ""],
            ["", "", "", "信新買", "", "", "100", "成行"],
            ["", "", "", "約定", "", "03/14 09:00:00", "bad", "100"],
            ["", "", "", "約定", "", "03/14 09:01:00", "60", "102"],
        ]
    )

    _assert_order_status_market_data_error(monkeypatch, trade, config, df)


def test_main_returns_error_code_for_trading_errors(monkeypatch, capsys):
    def raise_error():
        raise ProcessStateError("'HYPERSBI2' is running.")

    monkeypatch.setattr(trading_peripheral, "run", raise_error)

    assert trading_peripheral.main() == 1
    assert capsys.readouterr().out == "'HYPERSBI2' is running.\n"


def test_main_returns_error_code_for_config_errors(monkeypatch, capsys):
    def raise_error():
        raise ConfigError("missing section")

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
    except ScraperError as e:
        message = str(e)
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
    except ScraperError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ScraperError")

    assert message == (
        "News latest news XPath matched 2 nodes for "
        "https://example.com/news: //headline"
    )


def test_monitoring_does_not_mark_news_seen_when_email_is_not_sent(
    monkeypatch,
):
    trade = SimpleNamespace(config_directory="/tmp", config_path="/tmp/config")
    config = ConfigParser(interpolation=None)
    config["General"] = {
        "email_message_from": "",
        "email_message_to": "",
    }
    config["News"] = {
        "url": "https://example.com/news",
        "latest_news_xpath": "//headline",
        "latest_news_text": "",
    }
    response = _FakeResponse()
    write_calls = []

    class _NewsRoot:
        def xpath(self, expression):
            return [_FakeElement("Version 2")]

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
        lambda text: _NewsRoot(),
    )
    monkeypatch.setattr(
        app_monitoring,
        "write_config",
        lambda *args, **kwargs: write_calls.append((args, kwargs)),
    )

    app_monitoring.check_web_page_send_email_message(trade, config, "News")

    assert config["News"]["latest_news_text"] == ""
    assert write_calls == []


def test_monitoring_marks_news_seen_after_confirmed_email_send(monkeypatch):
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
    email_calls = []
    write_calls = []

    class _NewsRoot:
        def xpath(self, expression):
            return [_FakeElement("Version 2")]

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
        lambda text: _NewsRoot(),
    )
    monkeypatch.setattr(
        app_monitoring.google_services,
        "send_email_message",
        lambda *args: email_calls.append(args) or True,
    )
    monkeypatch.setattr(
        app_monitoring,
        "write_config",
        lambda *args, **kwargs: write_calls.append((args, kwargs)),
    )

    app_monitoring.check_web_page_send_email_message(trade, config, "News")

    assert config["News"]["latest_news_text"] == "Version 2"
    assert email_calls == [
        (
            app_monitoring.os.path.join("/tmp", "token.json"),
            "News",
            "from@example.com",
            "to@example.com",
            "Version 2\nhttps://example.com/news",
        )
    ]
    assert write_calls


def _build_maintenance_config():
    config = ConfigParser(interpolation=None)
    config["SBI Securities Maintenance Schedules"] = {
        "url": "https://example.com/maintenance",
        "timezone": "Asia/Tokyo",
        "last_inserted": "",
        "calendar_id": "",
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
        app_maintenance,
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
        app_maintenance,
        "write_config",
        lambda *args, **kwargs: None,
    )

    trading_peripheral.insert_maintenance_schedules(trade, config)

    assert response.encoding == "utf-8"


def test_insert_maintenance_schedules_persists_progress_on_insert_failure(
    monkeypatch,
):
    trade = _FakeMaintenanceTrade()
    config = _build_maintenance_config()
    config[trade.maintenance_schedules_section]["services"] = "('all',)"
    response = _FakeResponse()
    write_calls = []
    inserted_bodies = []

    class _FakeSchedule:
        def xpath(self, expression):
            if (
                expression
                == config[trade.maintenance_schedules_section][
                    "function_xpath"
                ]
            ):
                return [_FakeElement("Function")]
            if (
                expression
                == config[trade.maintenance_schedules_section][
                    "datetime_xpath"
                ]
            ):
                return [
                    _FakeElement(
                        "2026年3月14日（土）09:00～10:00\n"
                        "2026年3月14日（土）10:00～11:00"
                    )
                ]
            return []

    class _MaintenanceRoot:
        def xpath(self, expression):
            if expression == (
                config[trade.maintenance_schedules_section][
                    "service_xpath"
                ].format("all")
            ):
                return [_FakeSchedule()]
            return []

    def fail_second_insert(resource, calendar_id, body):
        inserted_bodies.append(body)
        if len(inserted_bodies) == 2:
            raise ExternalServiceError("insert failed")

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
    monkeypatch.setattr(
        app_maintenance.google_services,
        "insert_calendar_event",
        fail_second_insert,
    )
    monkeypatch.setattr(
        app_maintenance,
        "write_config",
        lambda *args, **kwargs: write_calls.append((args, kwargs)),
    )

    try:
        trading_peripheral.insert_maintenance_schedules(trade, config)
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == "insert failed"
    assert len(inserted_bodies) == 2
    assert write_calls
    assert (
        "09:00:00+09:00"
        in config[trade.maintenance_schedules_section]["previous_bodies"]
    )
    assert config[trade.maintenance_schedules_section]["last_inserted"] == ""


def test_insert_maintenance_schedules_retries_without_duplicate_events(
    monkeypatch,
):
    trade = _FakeMaintenanceTrade()
    inserted_ids = set()
    inserted_bodies = []

    class _FakeSchedule:
        def __init__(self, config):
            self.config = config

        def xpath(self, expression):
            section = self.config[trade.maintenance_schedules_section]
            if expression == section["function_xpath"]:
                return [_FakeElement("Function")]
            if expression == section["datetime_xpath"]:
                return [_FakeElement("2026年3月14日（土）09:00～10:00")]
            return []

    class _MaintenanceRoot:
        def __init__(self, config):
            self.config = config

        def xpath(self, expression):
            section = self.config[trade.maintenance_schedules_section]
            if expression == section["service_xpath"].format("all"):
                return [_FakeSchedule(self.config)]
            return []

    def build_config():
        config = _build_maintenance_config()
        section = config[trade.maintenance_schedules_section]
        section["calendar_id"] = "calendar"
        section["services"] = "('all',)"
        return config

    def insert_once_by_event_id(resource, calendar_id, body):
        event_id = body["id"]
        if event_id in inserted_ids:
            return None
        inserted_ids.add(event_id)
        inserted_bodies.append(body)
        return body

    monkeypatch.setattr(
        app_maintenance.web_utilities,
        "make_head_request",
        lambda url: SimpleNamespace(headers={}),
    )
    monkeypatch.setattr(
        app_maintenance.requests,
        "get",
        lambda url, timeout: _FakeResponse(),
    )
    monkeypatch.setattr(
        app_maintenance,
        "from_bytes",
        lambda content: SimpleNamespace(best=lambda: _FakeMatched()),
    )
    monkeypatch.setattr(
        app_maintenance.google_services,
        "get_calendar_resource",
        lambda *args: ("resource", "calendar"),
    )
    monkeypatch.setattr(
        app_maintenance.google_services,
        "insert_calendar_event",
        insert_once_by_event_id,
    )
    monkeypatch.setattr(
        app_maintenance,
        "write_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ExternalServiceError("config write failed")
        ),
    )

    for _ in range(2):
        config = build_config()
        monkeypatch.setattr(
            app_maintenance.html,
            "fromstring",
            lambda text, current_config=config: _MaintenanceRoot(
                current_config
            ),
        )
        try:
            trading_peripheral.insert_maintenance_schedules(trade, config)
        except ExternalServiceError as e:
            assert str(e) == "config write failed"
        else:
            raise AssertionError("Expected ExternalServiceError")

    assert len(inserted_bodies) == 1
    assert inserted_bodies[0]["id"]


def test_insert_maintenance_schedules_raises_for_missing_function_node(
    monkeypatch,
):
    trade = _FakeMaintenanceTrade()
    config = _build_maintenance_config()
    config[trade.maintenance_schedules_section]["services"] = "('all',)"
    response = _FakeResponse()
    write_calls = []

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
    monkeypatch.setattr(
        app_maintenance,
        "write_config",
        lambda *args, **kwargs: write_calls.append((args, kwargs)),
    )

    try:
        trading_peripheral.insert_maintenance_schedules(trade, config)
    except ScraperError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ScraperError")

    assert message == (
        "all maintenance function XPath matched 0 nodes for "
        "https://example.com/maintenance: following::p[1]"
    )
    assert config[trade.maintenance_schedules_section]["calendar_id"] == (
        "calendar"
    )
    assert write_calls

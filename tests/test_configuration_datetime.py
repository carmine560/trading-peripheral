from configparser import ConfigParser
from datetime import datetime
import re
from zoneinfo import ZoneInfo

from app.maintenance import _get_datetime_bounds, _replace_datetime
from core_utilities import config_diff, config_io, config_prompt
from core_utilities import datetime_utilities


def test_write_and_read_config_round_trip(tmp_path):
    config_path = tmp_path / "settings.ini"
    written = ConfigParser(interpolation=None)
    written["General"] = {
        "firefox_profile_directory": "C:/Firefox/Selenium",
        "wait_timeout": "4",
    }

    config_io.write_config(written, config_path.as_posix())

    loaded = ConfigParser(interpolation=None)
    config_io.read_config(loaded, config_path.as_posix())

    assert (
        loaded["General"]["firefox_profile_directory"] == "C:/Firefox/Selenium"
    )
    assert loaded["General"]["wait_timeout"] == "4"


def test_write_and_read_encrypted_config_uses_shared_file_helpers(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "settings.ini"
    encrypted_path = tmp_path / "settings.ini.gpg"
    encrypted_files = {}
    written = ConfigParser(interpolation=None)
    written["General"] = {
        "fingerprint": "fingerprint",
        "firefox_profile_directory": "C:/Firefox/Selenium",
    }

    def write_encrypted_file(path, data, fingerprint=""):
        encrypted_files[path] = (data, fingerprint)

    monkeypatch.setattr(
        config_io, "write_encrypted_file", write_encrypted_file
    )
    monkeypatch.setattr(
        config_io,
        "read_encrypted_file",
        lambda path: encrypted_files[path][0],
    )

    config_io.write_config(written, config_path.as_posix(), is_encrypted=True)
    encrypted_path.write_bytes(b"encrypted")

    loaded = ConfigParser(interpolation=None)
    config_io.read_config(loaded, config_path.as_posix(), is_encrypted=True)

    assert encrypted_files[encrypted_path.as_posix()][1] == "fingerprint"
    assert (
        loaded["General"]["firefox_profile_directory"] == "C:/Firefox/Selenium"
    )


def test_check_config_changes_resets_option_to_default(tmp_path, monkeypatch):
    config_path = tmp_path / "settings.ini"
    default_config = ConfigParser(interpolation=None)
    default_config["General"] = {
        "firefox_profile_directory": "C:/Firefox/Selenium",
        "wait_timeout": "4",
    }

    user_config = ConfigParser(interpolation=None)
    user_config["General"] = {
        "firefox_profile_directory": "C:/Firefox/Default",
        "wait_timeout": "4",
    }
    config_io.write_config(user_config, config_path.as_posix())

    monkeypatch.setattr(
        config_diff,
        "tidy_answer",
        lambda answers, level=0: "default",
    )

    config_diff.check_config_changes(default_config, config_path.as_posix())

    loaded = ConfigParser(interpolation=None)
    config_io.read_config(loaded, config_path.as_posix())
    assert loaded["General"].get("firefox_profile_directory") is None
    assert loaded["General"]["wait_timeout"] == "4"


def test_normalize_datetime_string_rolls_past_midnight():
    normalized = datetime_utilities.normalize_datetime_string(
        "2025-03-14 25:30"
    )

    assert normalized == "2025-03-15 01:30"


def test_get_datetime_bounds_rolls_time_only_end_past_midnight():
    section = {
        "datetime_regex": (
            r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日" r"（[^）]+）(\d{1,2}:\d{2})$"
        ),
        "year_group": "1",
        "month_group": "2",
        "day_group": "3",
        "time_group": "4",
    }

    start, end = _get_datetime_bounds(
        ["2026年3月14日（土）23:00", "02:00"],
        section,
        datetime(2026, 3, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        ZoneInfo("Asia/Tokyo"),
    )

    assert start.isoformat() == "2026-03-14T23:00:00+09:00"
    assert end.isoformat() == "2026-03-15T02:00:00+09:00"


def test_get_datetime_bounds_keeps_equal_start_and_end():
    section = {
        "datetime_regex": (
            r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日" r"（[^）]+）(\d{1,2}:\d{2})$"
        ),
        "year_group": "1",
        "month_group": "2",
        "day_group": "3",
        "time_group": "4",
    }

    start, end = _get_datetime_bounds(
        ["2026年3月14日（土）09:00", "09:00"],
        section,
        datetime(2026, 3, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
        ZoneInfo("Asia/Tokyo"),
    )

    assert start.isoformat() == "2026-03-14T09:00:00+09:00"
    assert end.isoformat() == "2026-03-14T09:00:00+09:00"


def test_replace_datetime_infers_next_year_for_old_dates():
    section = {
        "year_group": "1",
        "month_group": "2",
        "day_group": "3",
        "time_group": "4",
    }
    match = re.search(
        r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日（[^）]+）(\d{1,2}:\d{2})$",
        "1月1日（日）00:15",
    )

    result = _replace_datetime(
        match,
        section,
        datetime(2025, 12, 31, 23, 30, tzinfo=ZoneInfo("Asia/Tokyo")),
        ZoneInfo("Asia/Tokyo"),
    )

    assert result == "2026-1-1 00:15"


def test_replace_datetime_strips_year_suffix_when_present():
    section = {
        "year_group": "1",
        "month_group": "2",
        "day_group": "3",
        "time_group": "4",
    }
    match = re.search(
        r"^(\d{4}年)?(\d{1,2})月(\d{1,2})日（[^）]+）(\d{1,2}:\d{2})$",
        "2025年1月1日（日）00:15",
    )

    result = _replace_datetime(
        match,
        section,
        datetime(2025, 12, 31, 23, 30, tzinfo=ZoneInfo("Asia/Tokyo")),
        ZoneInfo("Asia/Tokyo"),
    )

    assert result == "2025-1-1 00:15"

from configparser import ConfigParser
from datetime import datetime
import re
from zoneinfo import ZoneInfo

from core_utilities import configuration, datetime_utilities
from trading_peripheral import _replace_datetime


def test_write_and_read_config_round_trip(tmp_path):
    config_path = tmp_path / "settings.ini"
    written = ConfigParser(interpolation=None)
    written["General"] = {"headless": "True", "implicitly_wait": "4"}

    configuration.write_config(written, config_path.as_posix())

    loaded = ConfigParser(interpolation=None)
    configuration.read_config(loaded, config_path.as_posix())

    assert loaded["General"]["headless"] == "True"
    assert loaded["General"]["implicitly_wait"] == "4"


def test_normalize_datetime_string_rolls_past_midnight():
    normalized = datetime_utilities.normalize_datetime_string(
        "2025-03-14 25:30"
    )

    assert normalized == "2025-03-15 01:30"


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

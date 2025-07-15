"""Perform date and time normalization, conversion, and related operations."""

from datetime import datetime, timedelta


def normalize_datetime_string(datetime_string):
    """Normalize a datetime string into a standard datetime string."""
    date_string, time_string = datetime_string.split()
    hour_string, minute_string = time_string.split(":")
    hour = int(hour_string)
    minute = int(minute_string)
    date = datetime.strptime(date_string, "%Y-%m-%d")
    if hour >= 24:
        days_offset = hour // 24
        hour = hour % 24
        date += timedelta(days=days_offset)

    normalized_datetime = date.replace(hour=hour, minute=minute)
    return normalized_datetime.strftime("%Y-%m-%d %H:%M")

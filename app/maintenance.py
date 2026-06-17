"""Maintenance schedule scraping and calendar insertion logic."""

import base64
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import hashlib
import os
import re
from zoneinfo import ZoneInfo

from charset_normalizer import from_bytes
from lxml import html
import requests

from core_utilities import (
    data_utilities,
    datetime_utilities,
    errors,
)
from core_utilities.config_io import write_config
from core_utilities.config_validation import (
    ensure_section_exists,
    evaluate_value,
)
from web_utilities import google_services, web_utilities


def _get_required_xpath_match(nodes, xpath, url, description):
    """Return the required unique XPath match or raise a scraper error."""
    if len(nodes) != 1:
        raise errors.ScraperError(
            f"{description} XPath matched {len(nodes)} nodes for {url}: "
            f"{xpath}"
        )
    return nodes[0]


def _replace_datetime(match_object, section, now, tzinfo):
    """Replace matched datetime strings with formatted strings."""
    matched_year = match_object.group(int(section["year_group"]))
    matched_month = match_object.group(int(section["month_group"]))
    matched_day = match_object.group(int(section["day_group"]))
    matched_time = match_object.group(int(section["time_group"]))
    if matched_year:
        matched_year = matched_year.removesuffix("年")
        return f"{matched_year}-{matched_month}-{matched_day} {matched_time}"

    assumed_year = int(now.strftime("%Y"))
    timedelta_object = (
        datetime.strptime(
            f"{assumed_year}-{matched_month}-{matched_day} {matched_time}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=tzinfo)
        - now
    )
    threshold = timedelta(days=365 - 30)
    if timedelta_object < -threshold:
        assumed_year += 1
    elif timedelta_object > threshold:
        assumed_year -= 1
    return f"{assumed_year}-{matched_month}-{matched_day} {matched_time}"


def _get_last_modified_datetime(url):
    """Return the parsed Last-Modified timestamp when HEAD data is usable."""
    try:
        head = web_utilities.make_head_request(url)
    except errors.ExternalServiceError:
        return None

    last_modified = head.headers.get("last-modified")
    if not last_modified:
        return None

    try:
        return parsedate_to_datetime(last_modified)
    except (TypeError, ValueError, IndexError):
        return None


def _get_response_root_title(url):
    """Fetch a page, then return the response, parsed root, and title."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise errors.ExternalServiceError(
            f"GET request failed for {url}: {e}"
        ) from e

    matched = from_bytes(response.content).best()
    response.encoding = matched.encoding if matched else "utf-8"
    root = html.fromstring(response.text)
    match_object = re.search("<title>(.*)</title>", response.text)
    title = match_object.group(1) if match_object else ""
    return response, root, title


def _get_datetime_bounds(datetime_range, section, now, tzinfo):
    """Parse a maintenance datetime range into start and end datetimes."""
    datetime_string = re.sub(
        section["datetime_regex"],
        lambda match_object: _replace_datetime(
            match_object, section, now, tzinfo
        ),
        datetime_range[0],
    )
    start = datetime.strptime(
        datetime_utilities.normalize_datetime_string(datetime_string),
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=tzinfo)
    if re.fullmatch(r"\d{1,2}:\d{2}", datetime_range[1]):
        datetime_string = start.strftime("%Y-%m-%d ") + datetime_range[1]
    else:
        datetime_string = re.sub(
            section["datetime_regex"],
            lambda match_object: _replace_datetime(
                match_object, section, now, tzinfo
            ),
            datetime_range[1],
        )

    end = datetime.strptime(
        datetime_utilities.normalize_datetime_string(datetime_string),
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=tzinfo)
    # Only roll over true overnight ranges; equal start and end are preserved.
    if end < start:
        end += timedelta(days=1)
    return start, end


def _store_maintenance_body(previous_bodies, service, body_tuple):
    """Store a calendar body tuple with bounded history per service."""
    previous_bodies.setdefault(service, []).append(body_tuple)
    maximum_number_of_bodies = 32
    if len(previous_bodies[service]) > maximum_number_of_bodies:
        previous_bodies[service] = previous_bodies[service][
            -maximum_number_of_bodies:
        ]


def _insert_service_maintenance_events(
    root,
    section,
    now,
    tzinfo,
    title,
    resource,
    previous_bodies,
):
    """Insert maintenance events from the parsed page into Calendar."""
    for service in evaluate_value(section["services"]):
        for schedule in root.xpath(section["service_xpath"].format(service)):
            function_element = _get_required_xpath_match(
                schedule.xpath(section["function_xpath"]),
                section["function_xpath"],
                section["url"],
                f"{service} maintenance function",
            )
            function = function_element.xpath("normalize-space(.)")
            datetime_element = _get_required_xpath_match(
                schedule.xpath(section["datetime_xpath"]),
                section["datetime_xpath"],
                section["url"],
                f"{service} maintenance datetime",
            )
            datetimes = datetime_element.text_content().split("\n")

            for datetime_text in datetimes:
                datetime_range = re.split(
                    re.compile(section["range_splitter_regex"]),
                    datetime_text.strip(),
                )
                if len(datetime_range) != 2:
                    continue

                start, end = _get_datetime_bounds(
                    datetime_range, section, now, tzinfo
                )
                body = {
                    "summary": f"🛠️ {service}: {function}",
                    "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": end.isoformat()},
                    "reminders": {"useDefault": False},
                    "source": {"title": title, "url": section["url"]},
                }
                body_tuple = data_utilities.dictionary_to_tuple(body)
                if body_tuple in previous_bodies.get(service, []):
                    continue

                # Derive a stable event ID so repeated inserts return 409
                # instead of duplicating.
                body["id"] = (
                    base64.b32hexencode(
                        hashlib.sha256(
                            repr(body_tuple).encode("utf-8")
                        ).digest()
                    )
                    .decode("ascii")
                    .rstrip("=")
                    .lower()
                )
                google_services.insert_calendar_event(
                    resource, section["calendar_id"], body
                )
                _store_maintenance_body(previous_bodies, service, body_tuple)


def insert_maintenance_schedules(trade, config):
    """Insert maintenance schedules into a Google Calendar."""
    ensure_section_exists(config, trade.maintenance_schedules_section)

    section = config[trade.maintenance_schedules_section]
    tzinfo = ZoneInfo(section["timezone"])
    now = datetime.now(tzinfo)

    head_last_modified = _get_last_modified_datetime(section["url"])
    last_inserted = (
        datetime.fromisoformat(section["last_inserted"])
        if section["last_inserted"]
        else datetime.min.replace(tzinfo=tzinfo)
    )
    last_inserted = max(last_inserted, now - timedelta(days=29))
    if head_last_modified is not None and head_last_modified <= last_inserted:
        return

    _, root, title = _get_response_root_title(section["url"])

    previous_calendar_id = section["calendar_id"]
    resource, section["calendar_id"] = google_services.get_calendar_resource(
        os.path.join(trade.config_directory, "token.json"),
        section["calendar_id"],
        trade.maintenance_schedules_section,
        section["timezone"],
        fingerprint=config["General"]["fingerprint"],
    )
    if not previous_calendar_id and section["calendar_id"]:
        write_config(config, trade.config_path)

    previous_bodies = evaluate_value(section["previous_bodies"])
    try:
        _insert_service_maintenance_events(
            root, section, now, tzinfo, title, resource, previous_bodies
        )
    except Exception:
        if str(previous_bodies) != section["previous_bodies"]:
            section["previous_bodies"] = str(previous_bodies)
            write_config(config, trade.config_path)
        raise
    section["previous_bodies"] = str(previous_bodies)

    section["last_inserted"] = now.isoformat()
    write_config(config, trade.config_path)

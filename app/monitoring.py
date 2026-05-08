"""Web page monitoring and email notification helpers."""

import os

from charset_normalizer import from_bytes
from lxml import html
import requests

from core_utilities import configuration, errors
from web_utilities import google_services


def _get_required_xpath_match(root, xpath, url, description):
    """Return the required unique XPath match or raise a scraper error."""
    matches = root.xpath(xpath)
    if len(matches) != 1:
        raise errors.ScraperError(
            f"{description} XPath matched {len(matches)} nodes for {url}: "
            f"{xpath}"
        )
    return matches[0]


def check_web_page_send_email_message(trade, config, section):
    """Check the web page and send an email message if an update is found."""
    configuration.ensure_section_exists(config, section)

    url = config[section]["url"]
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise errors.ExternalServiceError(
            f"GET request failed for {url}: {exc}"
        ) from exc

    matched = from_bytes(response.content).best()
    response.encoding = matched.encoding if matched else "utf-8"
    root = html.fromstring(response.text)

    latest_news_element = _get_required_xpath_match(
        root,
        config[section]["latest_news_xpath"],
        url,
        f"{section} latest news",
    )
    latest_news_text = latest_news_element.text_content().strip()
    if latest_news_text == config[section]["latest_news_text"]:
        return

    print(latest_news_text)

    google_services.send_email_message(
        os.path.join(trade.config_directory, "token.json"),
        section,
        config["General"]["email_message_from"],
        config["General"]["email_message_to"],
        f"{latest_news_text}\n{config[section]['url']}",
    )

    config[section]["latest_news_text"] = latest_news_text
    configuration.write_config(config, trade.config_path, is_encrypted=True)

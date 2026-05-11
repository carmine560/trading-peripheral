"""Manage SBI Securities data and integrate with other services."""

import inspect
import os
import sys
import time

from app import maintenance
from app.cli import get_arguments
from app.config import configure, configure_exit, ensure_watchlists_path
from app.maintenance import insert_maintenance_schedules
from app.monitoring import check_web_page_send_email_message
from app.order_status import (
    BROKERAGE_ORDER_STATUS_FUNCTIONS,
    extract_unsupported_brokerage_order_status,
)
from core_utilities import errors
from core_utilities import process_utilities
from core_utilities.config_common import ConfigError
from core_utilities.config_validation import ensure_section_exists
from core_utilities import file_utilities, initializer
from web_utilities import browser_driver

_replace_datetime = maintenance._replace_datetime


class Trade(initializer.Initializer):
    """Represent a trade process for a specific vendor."""

    def __init__(self, vendor, process):
        """Initialize the Trade with the vendor and process."""
        super().__init__(vendor, process, __file__)
        self.investment_tools_news_section = (
            f"{self.vendor} Investment Tools News"
        )
        self.maintenance_schedules_section = (
            f"{self.vendor} Maintenance Schedules"
        )
        self.order_status_section = f"{self.vendor} Order Status"
        self.brokerage_variables_section = f"{self.vendor} Variables"
        self.release_notes_section = f"{self.process} Release Notes"
        self.instruction_items = {
            "all_keys": initializer.extract_commands(
                inspect.getsource(browser_driver.execute_action)
            ),
            "control_flow_keys": {"exist", "for"},
            "additional_value_keys": {"send_keys"},
            "no_value_keys": {"refresh"},
        }


def _run_browser_actions(args, trade, config):
    """Execute browser-based actions using a Selenium WebDriver."""
    ensure_section_exists(config, trade.actions_section)
    max_attempts = 3
    retry_interval = 10
    # ChromeDriver may crash on an unsettled system after hibernation resume,
    # leaving the driver in a broken state, so wrap both 'initialize()' and
    # 'execute_action()' in the retry loop.
    for attempt in range(1, max_attempts + 1):
        driver = None
        try:
            driver = browser_driver.initialize(
                headless=config["General"].getboolean("headless"),
                user_data_directory=config["General"]["user_data_directory"],
                profile_directory=config["General"]["profile_directory"],
                implicitly_wait=float(config["General"]["implicitly_wait"]),
            )
            if args.s:
                browser_driver.execute_action(
                    driver,
                    config[trade.actions_section][
                        f"replace_{trade.vendor}_watchlists"
                    ],
                )
            if args.S:
                browser_driver.execute_action(
                    driver,
                    config[trade.actions_section][
                        f"replace_{trade.process}_watchlists"
                    ],
                )
            if args.o:
                browser_driver.execute_action(
                    driver, config[trade.actions_section]["get_order_status"]
                )
                if trade.vendor in BROKERAGE_ORDER_STATUS_FUNCTIONS:
                    BROKERAGE_ORDER_STATUS_FUNCTIONS[trade.vendor](
                        trade, config, driver
                    )
                else:
                    extract_unsupported_brokerage_order_status(trade.vendor)
            break
        except Exception as e:
            if attempt == max_attempts:
                raise
            print(
                f"Attempt {attempt} failed: {e}."
                f" Retrying in {retry_interval}s..."
            )
            time.sleep(retry_interval)
        finally:
            if driver is not None:
                driver.quit()


def _manage_snapshots(args, trade, config):
    """Archive or restore the process application data."""
    ensure_section_exists(config, trade.process)
    if process_utilities.is_running(trade.process):
        raise errors.ProcessStateError(f"'{trade.process}' is running.")
    application_data_directory = config[trade.process][
        "application_data_directory"
    ]
    snapshot_directory = config[trade.process]["snapshot_directory"]
    fingerprint = config["General"]["fingerprint"]
    if args.d:
        file_utilities.archive_encrypt_directory(
            application_data_directory,
            snapshot_directory,
            fingerprint=fingerprint,
        )
    if args.D:
        snapshot = os.path.join(
            snapshot_directory,
            os.path.basename(application_data_directory) + ".tar.xz.gpg",
        )
        output_directory = os.path.dirname(application_data_directory)
        file_utilities.decrypt_extract_file(snapshot, output_directory)


def run():
    """Execute the main program based on command-line arguments."""
    args = get_arguments()
    trade = Trade(*args.P)
    file_utilities.create_launchers_exit(args, __file__)
    configure_exit(args, trade)
    config = configure(trade)
    if args.t:
        check_web_page_send_email_message(
            trade, config, trade.investment_tools_news_section
        )
    if args.r:
        check_web_page_send_email_message(
            trade, config, trade.release_notes_section
        )
    if args.m:
        insert_maintenance_schedules(trade, config)
    if any((args.s, args.S, args.o)):
        _run_browser_actions(args, trade, config)
    if args.w:
        ensure_section_exists(config, trade.process)
        ensure_watchlists_path(config, trade)
        file_utilities.backup_file(
            config[trade.process]["watchlists"],
            backup_directory=config[trade.process]["backup_directory"],
        )
    if args.d or args.D:
        _manage_snapshots(args, trade, config)


def main():
    """Run the CLI and return the final process exit code."""
    try:
        run()
    except ConfigError as e:
        print(f"Configuration error: {e}")
        return 1
    except errors.TradingAssistantError as e:
        print(e)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

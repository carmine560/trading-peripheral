"""Manage SBI Securities data and integrate with other services."""

import os
import sys
import time

from app.cli import get_arguments
from app.config import configure, configure_exit, ensure_watchlists_path
from app.maintenance import insert_maintenance_schedules
from app.monitoring import check_web_page_send_email_message
from app.order_status import (
    BROKERAGE_ORDER_STATUS_FUNCTIONS,
    extract_unsupported_brokerage_order_status,
)
from core_utilities import (
    file_utilities,
    initializer,
    process_utilities,
)
from core_utilities.config_common import ConfigError
from core_utilities.config_validation import ensure_section_exists
from core_utilities.errors import (
    CoreUtilitiesError,
    ProcessStateError,
    UtilityOperationError,
)
from web_utilities import browser_driver

BROWSER_ACTION_MAX_ATTEMPTS = 3
BROWSER_ACTION_RETRY_INTERVAL = 10


class Trade(initializer.Initializer):
    """Represent a trade process for a specific vendor."""

    def __init__(self, vendor, process):
        """Initialize the Trade with the vendor and process."""
        super().__init__(vendor, process, __file__)
        self.maintenance_schedules_section = (
            f"{self.vendor} Maintenance Schedules"
        )
        self.order_status_section = f"{self.vendor} Order Status"
        self.brokerage_variables_section = f"{self.vendor} Variables"
        self.release_notes_section = f"{self.process} Release Notes"
        self.instruction_items = {
            "all_keys": list(browser_driver._COMMAND_DISPATCH),
            "control_flow_keys": {"exist", "for"},
            "additional_value_keys": {"send_keys"},
            "no_value_keys": {"refresh"},
        }


def _run_browser_actions(args, trade, config):
    """Execute browser-based actions using a Selenium WebDriver."""
    ensure_section_exists(config, trade.actions_section)
    # ChromeDriver may crash on an unsettled system after hibernation resume,
    # leaving the driver in a broken state, so wrap both initialize() and
    # execute_action() in the retry loop.
    for attempt in range(1, BROWSER_ACTION_MAX_ATTEMPTS + 1):
        driver = None
        try:
            driver = browser_driver.initialize(
                headless=config["General"].getboolean("headless"),
                user_data_directory=config["General"]["user_data_directory"],
                profile_directory=config["General"]["profile_directory"],
            )
            if args.s:
                browser_driver.execute_action(
                    driver,
                    config[trade.actions_section][
                        f"replace_{trade.vendor}_watchlists"
                    ],
                    wait_timeout=float(config["General"]["wait_timeout"]),
                )
            if args.S:
                browser_driver.execute_action(
                    driver,
                    config[trade.actions_section][
                        f"replace_{trade.process}_watchlists"
                    ],
                    wait_timeout=float(config["General"]["wait_timeout"]),
                )
            if args.o:
                browser_driver.execute_action(
                    driver,
                    config[trade.actions_section]["get_order_status"],
                    wait_timeout=float(config["General"]["wait_timeout"]),
                )
                if trade.vendor in BROKERAGE_ORDER_STATUS_FUNCTIONS:
                    BROKERAGE_ORDER_STATUS_FUNCTIONS[trade.vendor](
                        trade, config, driver
                    )
                else:
                    extract_unsupported_brokerage_order_status(trade.vendor)
            break
        except Exception as e:
            if attempt == BROWSER_ACTION_MAX_ATTEMPTS:
                raise
            print(
                f"Attempt {attempt} failed: {e}\n"
                f"Retrying in {BROWSER_ACTION_RETRY_INTERVAL}s..."
            )
            time.sleep(BROWSER_ACTION_RETRY_INTERVAL)
        finally:
            if driver is not None:
                driver.quit()


def _manage_snapshots(args, trade, config):
    """Archive or restore the process application data."""
    ensure_section_exists(config, trade.process)
    if process_utilities.is_running(trade.process):
        raise ProcessStateError(f"'{trade.process}' is running.")
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
    if file_utilities.create_launchers_exit(args, __file__):
        return
    configure_exit(args, trade)
    config = configure(trade)
    if args.r:
        check_web_page_send_email_message(
            trade, config, trade.release_notes_section
        )
    if args.m:
        insert_maintenance_schedules(trade, config)
    if any((args.s, args.S, args.o)):
        _run_browser_actions(args, trade, config)
    if args.w:
        ensure_watchlists_path(config, trade)
        watchlists = config[trade.process]["watchlists"]
        if not os.path.isfile(watchlists):
            raise UtilityOperationError(
                f"Watchlist file does not exist: {watchlists}"
            )
        file_utilities.backup_file(
            watchlists,
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
    except CoreUtilitiesError as e:
        print(e)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

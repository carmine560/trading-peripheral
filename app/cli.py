"""Command-line parsing for the trading peripheral entrypoint."""

import argparse
import sys

from core_utilities import file_utilities


def get_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser()
    config_group = parser.add_mutually_exclusive_group()
    snapshot_group = parser.add_mutually_exclusive_group()

    parser.add_argument(
        "-P",
        nargs=2,
        default=("SBI Securities", "HYPERSBI2"),
        help="set the brokerage and the process [defaults: %(default)s]",
        metavar=("BROKERAGE", "PROCESS|EXECUTABLE_PATH"),
    )
    parser.add_argument(
        "-r",
        action="store_true",
        help="check the 'PROCESS' release notes"
        " and send a notification via Gmail if they are updated",
    )
    parser.add_argument(
        "-m",
        action="store_true",
        help="insert 'PROCESS' maintenance schedules into Google Calendar",
    )
    parser.add_argument(
        "-s",
        action="store_true",
        help="replace watchlists on the 'BROKERAGE' website"
        " with the 'PROCESS' watchlists",
    )
    parser.add_argument(
        "-S",
        action="store_true",
        help="replace the 'PROCESS' watchlists"
        " with watchlists on the 'BROKERAGE' website",
    )
    parser.add_argument(
        "-o",
        action="store_true",
        help="extract the order status"
        " from the 'BROKERAGE' order status web page"
        " and copy it to the clipboard",
    )
    parser.add_argument(
        "-w", action="store_true", help="backup the 'PROCESS' watchlists"
    )
    snapshot_group.add_argument(
        "-d",
        action="store_true",
        help="take a snapshot of the 'PROCESS' application data",
    )
    snapshot_group.add_argument(
        "-D",
        action="store_true",
        help="restore the 'PROCESS' application data from a snapshot",
    )

    file_utilities.add_launcher_options(config_group)
    config_group.add_argument(
        "-G", action="store_true", help="configure general options and exit"
    )
    config_group.add_argument(
        "-O",
        action="store_true",
        help="configure order status formats and exit",
    )
    config_group.add_argument(
        "-A", action="store_true", help="configure actions and exit"
    )
    config_group.add_argument(
        "-C", action="store_true", help="check configuration changes and exit"
    )

    return parser.parse_args(None if sys.argv[1:] else ["-h"])

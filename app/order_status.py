"""Order-status extraction and brokerage dispatch helpers."""

from io import StringIO
import re
import sys

import pandas as pd

from core_utilities import configuration


def extract_sbi_securities_order_status(trade, config, driver):
    """Extract order status from a webpage and copy it to the clipboard."""
    # The SBI order status consists of a summary row, an order detail row, and
    # an execution row.
    order_detail_row_offset = 1
    execution_row_offset = 2
    rows_per_execution_block = 3
    section = config[trade.order_status_section]

    try:
        dfs = pd.read_html(
            StringIO(driver.page_source),
            match=section["table_identifier"],
            flavor="lxml",
        )
    except ValueError as exc:
        print(exc)
        sys.exit(1)

    exclusion = configuration.evaluate_value(section["exclusion"])
    df = min(dfs, key=lambda frame: frame.shape[0])
    df = df[
        ~df.iloc[:, int(exclusion["equals"][0])].isin(exclusion["equals"][1])
        & ~df.iloc[:, int(exclusion["startswith"][0])].str.startswith(
            exclusion["startswith"][1]
        )
    ]
    size_price = pd.DataFrame(columns=("size", "price"))

    index = 0
    order_trigger_column = int(section["order_trigger_column"])
    symbol_column = int(section["symbol_column"])
    margin_transaction_type_column = int(
        section["margin_transaction_type_column"]
    )
    order_type_column = int(section["order_type_column"])
    execution_column = int(section["execution_column"])
    datetime_column = int(section["datetime_column"])
    size_column = int(section["size_column"])
    price_column = int(section["price_column"])
    output_columns = configuration.evaluate_value(section["output_columns"])
    entry_date = None
    entry_time = None
    order_specification = None
    entry_price = None
    results = pd.DataFrame(columns=output_columns)

    while index < len(df):
        if df.iloc[index, execution_column] == section["execution"]:
            if len(size_price) == 0:
                size_price.loc[0] = [
                    df.iloc[index - 1, size_column],
                    df.iloc[index - 1, price_column],
                ]

            size_price.loc[len(size_price)] = [
                df.iloc[index, size_column],
                df.iloc[index, price_column],
            ]
            if (
                index + 1 == len(df)
                or df.iloc[index + 1, execution_column] != section["execution"]
            ):
                size_price_index = 0
                size_price = size_price.astype(float)
                summation = 0
                while size_price_index < len(size_price):
                    summation += (
                        size_price.loc[size_price_index, "size"]
                        * size_price.loc[size_price_index, "price"]
                    )
                    size_price_index += 1

                average_price = summation / size_price["size"].sum()
                # 3 decimals preserves weighted-average precision without
                # implying sub-tick prices.
                average_price = f"{average_price:.3f}".rstrip("0").rstrip(".")
                if df.iloc[
                    index - len(size_price), margin_transaction_type_column
                ].startswith(section["margin_entry_prefix"]):
                    entry_price = average_price
                else:
                    results.loc[len(results) - 1, "exit_price"] = average_price

                size_price = pd.DataFrame(columns=("size", "price"))

            index += 1
        else:
            symbol = re.sub(
                section["symbol_regex"],
                section["symbol_replacement"],
                df.iloc[index, symbol_column],
            )
            size = df.iloc[index + order_detail_row_offset, size_column]
            if df.iloc[
                index + order_detail_row_offset, margin_transaction_type_column
            ].startswith(section["margin_entry_prefix"]):
                entry_date = re.sub(
                    section["datetime_regex"],
                    section["date_replacement"],
                    df.iloc[index + execution_row_offset, datetime_column],
                )
                entry_time = re.sub(
                    section["datetime_regex"],
                    section["time_replacement"],
                    df.iloc[index + execution_row_offset, datetime_column],
                )

                position = (
                    "long"
                    if df.iloc[
                        index + order_detail_row_offset,
                        margin_transaction_type_column,
                    ].startswith(section["margin_long_entry"])
                    else "short"
                )
                order_trigger = (
                    "stop"
                    if df.iloc[index, order_trigger_column]
                    == section["stop_order"]
                    else ""
                )
                order_type = (
                    "market order"
                    if df.iloc[
                        index + order_detail_row_offset, order_type_column
                    ]
                    == section["market_order"]
                    else "limit order"
                )
                order_specification = " ".join(
                    part
                    for part in [position, order_trigger, order_type]
                    if part
                )

                entry_price = df.iloc[
                    index + execution_row_offset, price_column
                ]
            else:
                exit_time = re.sub(
                    section["datetime_regex"],
                    section["time_replacement"],
                    df.iloc[index + execution_row_offset, datetime_column],
                )
                exit_price = df.iloc[
                    index + execution_row_offset, price_column
                ]

                results.loc[len(results)] = [
                    {
                        "entry_date": entry_date,
                        "entry_time": entry_time,
                        "symbol": symbol,
                        "size": size,
                        "order_specification": order_specification,
                        "entry_price": entry_price,
                        "exit_time": exit_time,
                        "exit_price": exit_price,
                    }.get(column)
                    for column in output_columns
                ]

            index += rows_per_execution_block

    if len(results) == 1:
        results = results.reindex([0, 1])

    results.to_clipboard(sep=",", header=False, index=False, quoting=1)


def extract_unsupported_brokerage_order_status(brokerage):
    """Handle order status requests for unsupported brokerages."""
    print(f"Order status extraction for '{brokerage}' is not implemented.")
    return None


BROKERAGE_ORDER_STATUS_FUNCTIONS = {
    "SBI Securities": extract_sbi_securities_order_status,
}

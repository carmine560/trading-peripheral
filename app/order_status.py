"""Order-status extraction and brokerage dispatch helpers."""

from io import StringIO
import re

import pandas as pd

from core_utilities.config_validation import evaluate_value
from core_utilities.errors import MarketDataError

# The SBI order status consists of a summary row, an order detail row, and an
# execution row.
SBI_SECURITIES_ORDER_DETAIL_ROW_OFFSET = 1
SBI_SECURITIES_EXECUTION_ROW_OFFSET = 2
SBI_SECURITIES_ROWS_PER_EXECUTION_BLOCK = 3


def extract_sbi_securities_order_status(trade, config, driver):
    """Extract order status from a webpage and copy it to the clipboard."""
    section = config[trade.order_status_section]

    try:
        dfs = pd.read_html(
            StringIO(driver.page_source),
            match=section["table_identifier"],
            flavor="lxml",
        )
    except ValueError as e:
        raise MarketDataError(
            "Unable to parse the order status table from the current page."
        ) from e

    try:
        exclusion = evaluate_value(section["exclusion"])
        df = min(dfs, key=lambda frame: frame.shape[0])
        startswith_column = int(exclusion["startswith"][0])
        startswith_values = (
            df.iloc[:, startswith_column]
            .fillna("")
            .astype(str)
            .str.startswith(exclusion["startswith"][1])
        )
        df = df[
            ~df.iloc[:, int(exclusion["equals"][0])].isin(
                exclusion["equals"][1]
            )
            & ~startswith_values
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
        output_columns = evaluate_value(section["output_columns"])
        entry_date = None
        entry_time = None
        order_specification = None
        entry_price = None
        results = []

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
                    or df.iloc[index + 1, execution_column]
                    != section["execution"]
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
                    average_price = f"{average_price:.3f}".rstrip("0")
                    average_price = average_price.rstrip(".")
                    transaction_type = str(
                        df.iloc[
                            index - len(size_price),
                            margin_transaction_type_column,
                        ]
                    )
                    if transaction_type.startswith(
                        section["margin_entry_prefix"]
                    ):
                        entry_price = average_price
                    else:
                        results[-1]["exit_price"] = average_price

                    size_price = pd.DataFrame(columns=("size", "price"))

                index += 1
            else:
                symbol = re.sub(
                    section["symbol_regex"],
                    section["symbol_replacement"],
                    str(df.iloc[index, symbol_column]),
                )
                size = df.iloc[
                    index + SBI_SECURITIES_ORDER_DETAIL_ROW_OFFSET, size_column
                ]
                transaction_type = str(
                    df.iloc[
                        index + SBI_SECURITIES_ORDER_DETAIL_ROW_OFFSET,
                        margin_transaction_type_column,
                    ]
                )
                if transaction_type.startswith(section["margin_entry_prefix"]):
                    datetime_value = str(
                        df.iloc[
                            index + SBI_SECURITIES_EXECUTION_ROW_OFFSET,
                            datetime_column,
                        ]
                    )
                    entry_date = re.sub(
                        section["datetime_regex"],
                        section["date_replacement"],
                        datetime_value,
                    )
                    entry_time = re.sub(
                        section["datetime_regex"],
                        section["time_replacement"],
                        datetime_value,
                    )

                    position = (
                        "long"
                        if transaction_type.startswith(
                            section["margin_long_entry"]
                        )
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
                            index + SBI_SECURITIES_ORDER_DETAIL_ROW_OFFSET,
                            order_type_column,
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
                        index + SBI_SECURITIES_EXECUTION_ROW_OFFSET,
                        price_column,
                    ]
                else:
                    exit_time = re.sub(
                        section["datetime_regex"],
                        section["time_replacement"],
                        str(
                            df.iloc[
                                index + SBI_SECURITIES_EXECUTION_ROW_OFFSET,
                                datetime_column,
                            ]
                        ),
                    )
                    exit_price = df.iloc[
                        index + SBI_SECURITIES_EXECUTION_ROW_OFFSET,
                        price_column,
                    ]

                    results.append(
                        {
                            "entry_date": entry_date,
                            "entry_time": entry_time,
                            "symbol": symbol,
                            "size": size,
                            "order_specification": order_specification,
                            "entry_price": entry_price,
                            "exit_time": exit_time,
                            "exit_price": exit_price,
                        }
                    )

                index += SBI_SECURITIES_ROWS_PER_EXECUTION_BLOCK

        results = pd.DataFrame(results, columns=output_columns)
        if len(results) == 1:
            results = results.reindex([0, 1])
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
        raise MarketDataError(
            "Unable to extract order status from the parsed table."
        ) from e

    results.to_clipboard(sep=",", header=False, index=False, quoting=1)


def extract_unsupported_brokerage_order_status(brokerage):
    """Handle order status requests for unsupported brokerages."""
    raise MarketDataError(
        f"Order status extraction for '{brokerage}' is not implemented."
    )


BROKERAGE_ORDER_STATUS_FUNCTIONS = {
    "SBI Securities": extract_sbi_securities_order_status,
}

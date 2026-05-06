#!/usr/bin/env python3
"""
Build a standalone interactive stock price dashboard from downloaded parquet data.

The dashboard is written as a single HTML file and does not require a local
server or JavaScript package installation. The HTML shell lives in
scripts/stock_price_dashboard_template.html.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOWNLOAD_DIR = PROJECT_ROOT / "downloaded_stock_data"
DAILY_HISTORY_DIR_NAME = "daily_history"
DEFAULT_DATA_DIR = DEFAULT_DOWNLOAD_DIR / DAILY_HISTORY_DIR_NAME
DEFAULT_OUTPUT = PROJECT_ROOT / "stock_price_dashboard.html"
DEFAULT_STOCK_LIST_FILE = PROJECT_ROOT / "config" / "tracked_stocks.csv"
MINUTE_NS = 60_000_000_000


TEMPLATE_PATH = Path(__file__).with_name("stock_price_dashboard_template.html")
DATA_PLACEHOLDER = "__DATA__"


def project_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def resolve_data_dir(path: Path) -> Path:
    if path.name == DAILY_HISTORY_DIR_NAME:
        return path

    daily_history_dir = path / DAILY_HISTORY_DIR_NAME
    if daily_history_dir.exists():
        return daily_history_dir

    return path


def read_stock_names(stock_list_path: Path) -> dict[str, str]:
    if not stock_list_path.exists():
        raise ValueError(f"Tracked stock list not found at {stock_list_path}")

    with stock_list_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"Tracked stock list is empty: {stock_list_path}")

        fields_by_name = {field.strip().lower(): field for field in reader.fieldnames}
        if "symbol" not in fields_by_name:
            raise ValueError(
                f"Tracked stock list must include a symbol column: {stock_list_path}"
            )

        symbol_field = fields_by_name["symbol"]
        name_field = fields_by_name.get("name")
        enabled_field = fields_by_name.get("enabled")
        names: dict[str, str] = {}

        for row in reader:
            symbol = (row.get(symbol_field) or "").strip().upper()
            if not symbol:
                continue

            enabled = (row.get(enabled_field) or "true").strip().lower()
            if enabled in {"0", "false", "f", "no", "n", "off"}:
                continue

            name = (row.get(name_field) or "").strip() if name_field else ""
            if name:
                names[symbol] = name

    return names


def read_stock_points(
    data_dir: Path,
    batch_size: int,
    stock_names: dict[str, str],
) -> dict[str, dict[str, Any]]:
    try:
        import pandas as pd
        import pyarrow.dataset as ds
    except ImportError as exc:
        raise RuntimeError(
            "pandas and pyarrow are required. Install dependencies in the venv first."
        ) from exc

    parquet_files = list(data_dir.rglob("*.parquet"))
    if not parquet_files:
        raise ValueError(f"No parquet files found under {data_dir}")

    dataset = ds.dataset(str(data_dir), format="parquet", partitioning="hive")
    schema_names = set(dataset.schema.names)
    required = {"symbol", "timestamp", "price"}
    missing = sorted(required - schema_names)
    if missing:
        raise ValueError(f"Missing required parquet columns: {', '.join(missing)}")

    columns = ["symbol", "timestamp", "price"]
    if "short_name" in schema_names:
        columns.append("short_name")

    points_by_symbol: dict[str, dict[int, tuple[int, float]]] = defaultdict(dict)
    names_by_symbol: dict[str, str] = {}
    rows_seen = 0
    batches_seen = 0

    scanner = dataset.scanner(columns=columns, batch_size=batch_size, use_threads=True)
    for batch in scanner.to_batches():
        batches_seen += 1
        df = batch.to_pandas()
        rows_seen += len(df)
        if df.empty:
            continue

        df = df.dropna(subset=["symbol", "timestamp", "price"])
        if df.empty:
            continue

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.dropna(subset=["timestamp"])
        if df.empty:
            continue

        df["timestamp_ns"] = df["timestamp"].astype("int64")
        df["minute_ms"] = (df["timestamp_ns"] // MINUTE_NS) * 60_000
        df = df.sort_values("timestamp_ns").drop_duplicates(
            ["symbol", "minute_ms"], keep="last"
        )

        has_name = "short_name" in df.columns
        for row in df.itertuples(index=False):
            symbol = str(row.symbol)
            price = float(row.price)
            minute_ms = int(row.minute_ms)
            timestamp_ns = int(row.timestamp_ns)

            existing = points_by_symbol[symbol].get(minute_ms)
            if existing is None or timestamp_ns >= existing[0]:
                points_by_symbol[symbol][minute_ms] = (timestamp_ns, price)

            if has_name:
                short_name = getattr(row, "short_name", None)
                if short_name and symbol not in names_by_symbol:
                    names_by_symbol[symbol] = str(short_name)

        if batches_seen % 2_000 == 0:
            print(
                f"processed {batches_seen:,} parquet batches, "
                f"{rows_seen:,} raw rows",
                flush=True,
            )

    if not points_by_symbol:
        raise ValueError(f"No usable stock rows found under {data_dir}")

    stock_data: dict[str, dict[str, Any]] = {}
    for symbol, minute_points in sorted(points_by_symbol.items()):
        sorted_points = sorted(minute_points.items())
        stock_data[symbol] = {
            "name": stock_names.get(symbol) or names_by_symbol.get(symbol, symbol),
            "t": [minute_ms for minute_ms, _point in sorted_points],
            "p": [round(point[1], 4) for _minute_ms, point in sorted_points],
            "count": len(sorted_points),
        }

    for symbol, name in sorted(stock_names.items()):
        stock_data.setdefault(
            symbol,
            {
                "name": name or symbol,
                "t": [],
                "p": [],
                "count": 0,
            },
        )

    return stock_data


def downsample_stock_data(
    stock_data: dict[str, dict[str, Any]],
    max_points_per_symbol: int,
) -> dict[str, dict[str, Any]]:
    if max_points_per_symbol <= 0:
        return stock_data

    for points in stock_data.values():
        count = len(points["t"])
        if count <= max_points_per_symbol:
            continue

        step = (count - 1) / (max_points_per_symbol - 1)
        indexes = sorted({round(i * step) for i in range(max_points_per_symbol)})
        points["t"] = [points["t"][index] for index in indexes]
        points["p"] = [points["p"][index] for index in indexes]
        points["count"] = len(indexes)

    return stock_data


def read_html_template() -> str:
    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"HTML template not found at {TEMPLATE_PATH}") from exc

    if DATA_PLACEHOLDER not in template:
        raise ValueError(f"HTML template must contain {DATA_PLACEHOLDER}")

    return template


def write_dashboard(stock_data: dict[str, dict[str, Any]], output_path: Path) -> None:
    data_json = json.dumps(stock_data, separators=(",", ":"))
    template = read_html_template()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        template.replace(DATA_PLACEHOLDER, data_json),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an interactive stock price HTML dashboard from parquet files."
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Folder containing daily_history parquet files. Defaults to downloaded_stock_data/daily_history.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="HTML file to write. Defaults to stock_price_dashboard.html.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250_000,
        help="PyArrow scanner batch size.",
    )
    parser.add_argument(
        "--max-points-per-symbol",
        type=int,
        default=0,
        help="Optionally downsample each symbol after minute aggregation. 0 keeps all points.",
    )
    parser.add_argument(
        "--stock-list-file",
        default=str(DEFAULT_STOCK_LIST_FILE),
        help="CSV file with symbol/name metadata. Defaults to config/tracked_stocks.csv.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = resolve_data_dir(project_relative_path(args.data_dir)).resolve()
    output_path = project_relative_path(args.output).resolve()
    stock_list_path = project_relative_path(args.stock_list_file).resolve()

    try:
        stock_names = read_stock_names(stock_list_path)
        stock_data = read_stock_points(data_dir, args.batch_size, stock_names)
        stock_data = downsample_stock_data(stock_data, args.max_points_per_symbol)
        write_dashboard(stock_data, output_path)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}")
        return 1

    symbol_count = len(stock_data)
    point_count = sum(points["count"] for points in stock_data.values())
    print(f"wrote {output_path}")
    print(f"included {point_count:,} minute-level points across {symbol_count} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

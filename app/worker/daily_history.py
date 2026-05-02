import os
import tempfile
from argparse import ArgumentParser, Namespace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import boto3
import pandas as pd
import yfinance as yf


EASTERN_TZ = ZoneInfo("America/New_York")
DEFAULT_INTERVAL = "1m"
DEFAULT_PERIOD = "1d"
NOTIFY_TOPIC_ARN = os.environ.get("NOTIFY_TOPIC_ARN")


def log(message: str) -> None:
    now = datetime.now(EASTERN_TZ).isoformat()
    print(f"[{now}] {message}", flush=True)


def publish_notification(subject: str, details: dict[str, Any]) -> None:
    if not NOTIFY_TOPIC_ARN:
        return

    timestamp = datetime.now(EASTERN_TZ).isoformat()
    message_lines = [subject, f"timestamp={timestamp}"]
    message_lines.extend(f"{key}={value}" for key, value in details.items())

    try:
        boto3.client("sns").publish(
            TopicArn=NOTIFY_TOPIC_ARN,
            Subject=subject[:100],
            Message="\n".join(message_lines),
        )
    except Exception as exc:
        log(f"[WARN] Failed to publish SNS notification: {exc}")


def stock_list_from_env() -> list[str]:
    stock_list = os.environ.get("STOCK_LIST", "")
    return [symbol.strip() for symbol in stock_list.split(",") if symbol.strip()]


def parse_args() -> Namespace:
    parser = ArgumentParser(
        description=(
            "Fetch end-of-day intraday bars with yfinance and write one parquet "
            "file to S3."
        )
    )
    parser.add_argument(
        "--symbols",
        default=",".join(stock_list_from_env()),
        help="Comma-separated symbols. Defaults to STOCK_LIST.",
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("S3_BUCKET"),
        help="Destination S3 bucket. Defaults to S3_BUCKET.",
    )
    parser.add_argument(
        "--interval",
        default=os.environ.get("YF_INTERVAL", DEFAULT_INTERVAL),
        help="yfinance interval. Defaults to 1m, which is yfinance's finest historical interval.",
    )
    parser.add_argument(
        "--period",
        default=os.environ.get("YF_PERIOD", DEFAULT_PERIOD),
        help="yfinance period used when --date is omitted. Defaults to 1d.",
    )
    parser.add_argument(
        "--date",
        help=(
            "Optional market date to fetch in YYYY-MM-DD format. Useful for "
            "manual backfills within yfinance's 1m retention window."
        ),
    )
    parser.add_argument(
        "--include-prepost",
        action="store_true",
        default=os.environ.get("YF_INCLUDE_PREPOST", "").lower() == "true",
        help="Include pre-market and post-market bars.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and normalize data without uploading to S3.",
    )
    return parser.parse_args()


def parse_symbols(value: str) -> list[str]:
    symbols = [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
    if not symbols:
        raise ValueError("at least one stock symbol is required")
    return symbols


def market_date_range(value: str) -> tuple[date, date]:
    start = date.fromisoformat(value)
    return start, start + timedelta(days=1)


def download_history(
    symbols: list[str],
    interval: str,
    period: str,
    target_date: str | None,
    include_prepost: bool,
) -> pd.DataFrame:
    ticker_arg = " ".join(symbols)
    log(
        "Downloading yfinance history: "
        f"symbols={ticker_arg}, interval={interval}, "
        f"period={period if target_date is None else 'date-range'}, "
        f"include_prepost={include_prepost}"
    )

    kwargs = {
        "tickers": ticker_arg,
        "interval": interval,
        "group_by": "ticker",
        "auto_adjust": False,
        "threads": True,
        "prepost": include_prepost,
        "progress": False,
    }

    if target_date:
        start, end = market_date_range(target_date)
        kwargs["start"] = start.isoformat()
        kwargs["end"] = end.isoformat()
    else:
        kwargs["period"] = period

    return yf.download(**kwargs)


def as_eastern_series(values: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(values, errors="coerce")
    if timestamps.dt.tz is None:
        return timestamps.dt.tz_localize(EASTERN_TZ)
    return timestamps.dt.tz_convert(EASTERN_TZ)


def flatten_symbol_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()

    result = frame.reset_index()
    timestamp_column = result.columns[0]
    result = result.rename(
        columns={
            timestamp_column: "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    keep_columns = [
        column
        for column in ["timestamp", "open", "high", "low", "close", "adj_close", "volume"]
        if column in result.columns
    ]
    result = result[keep_columns].copy()
    result["symbol"] = symbol
    return result


def normalize_history(raw: pd.DataFrame, symbols: list[str], interval: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    if isinstance(raw.columns, pd.MultiIndex):
        top_level = set(raw.columns.get_level_values(0))
        second_level = set(raw.columns.get_level_values(1))

        for symbol in symbols:
            if symbol in top_level:
                frames.append(flatten_symbol_frame(raw[symbol], symbol))
            elif symbol in second_level:
                frames.append(flatten_symbol_frame(raw.xs(symbol, axis=1, level=1), symbol))
            else:
                log(f"No yfinance rows returned for {symbol}")
    else:
        if len(symbols) != 1:
            raise ValueError("unexpected single-symbol yfinance response for multiple symbols")
        frames.append(flatten_symbol_frame(raw, symbols[0]))

    if not frames:
        return pd.DataFrame()

    history = pd.concat(frames, ignore_index=True)
    history = history.dropna(subset=["timestamp", "close"])
    if history.empty:
        return pd.DataFrame()

    timestamps = as_eastern_series(history["timestamp"])
    history["timestamp"] = timestamps.map(lambda value: value.isoformat())
    history["trading_date"] = timestamps.dt.date.astype(str)
    history["price"] = history["close"].astype(float)
    history["interval"] = interval
    history["source"] = "yfinance"
    history["fetched_at"] = datetime.now(EASTERN_TZ).isoformat()

    ordered_columns = [
        "symbol",
        "timestamp",
        "trading_date",
        "price",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "interval",
        "source",
        "fetched_at",
    ]
    existing_columns = [column for column in ordered_columns if column in history.columns]
    history = history[existing_columns]
    return history.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def s3_key_for_history(history: pd.DataFrame, interval: str) -> str:
    if history.empty:
        raise ValueError("cannot build S3 key for empty history")

    trading_dates = sorted(history["trading_date"].dropna().unique())
    key_date = date.fromisoformat(str(trading_dates[-1]))
    return (
        f"daily_history/year={key_date:%Y}/month={key_date:%m}/day={key_date:%d}/"
        f"stocks-{interval}.parquet"
    )


def upload_history(history: pd.DataFrame, bucket: str, interval: str, dry_run: bool) -> str:
    key = s3_key_for_history(history, interval)
    log(
        f"Prepared {len(history)} rows across {history['symbol'].nunique()} symbols "
        f"for s3://{bucket}/{key}"
    )

    if dry_run:
        return key

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        history.to_parquet(temp_path, compression="snappy", index=False)
        boto3.client("s3").upload_file(str(temp_path), bucket, key)
    finally:
        temp_path.unlink(missing_ok=True)

    log(f"Uploaded daily history to s3://{bucket}/{key}")
    return key


def main() -> int:
    args = parse_args()

    try:
        if not args.bucket and not args.dry_run:
            raise ValueError("S3 bucket is required unless --dry-run is set")

        symbols = parse_symbols(args.symbols)
        publish_notification(
            "Stock daily history started",
            {
                "symbols": ",".join(symbols),
                "interval": args.interval,
                "period": args.period if args.date is None else "date-range",
                "target_date": args.date or "",
                "include_prepost": args.include_prepost,
                "dry_run": args.dry_run,
            },
        )

        raw = download_history(
            symbols=symbols,
            interval=args.interval,
            period=args.period,
            target_date=args.date,
            include_prepost=args.include_prepost,
        )
        history = normalize_history(raw, symbols, args.interval)

        if history.empty:
            log("No yfinance history returned; skipping S3 upload")
            publish_notification(
                "Stock daily history finished with no data",
                {
                    "symbols": ",".join(symbols),
                    "interval": args.interval,
                    "bucket": args.bucket or "dry-run",
                },
            )
            return 0

        bucket = args.bucket or "dry-run"
        key = upload_history(history, bucket, args.interval, args.dry_run)
        publish_notification(
            "Stock daily history finished",
            {
                "symbols": ",".join(symbols),
                "rows": len(history),
                "symbol_count": history["symbol"].nunique(),
                "bucket": bucket,
                "key": key,
            },
        )
        return 0
    except Exception as exc:
        log(f"Daily history job failed: {exc}")
        publish_notification(
            "Stock daily history failed",
            {
                "error": str(exc),
                "symbols": args.symbols,
                "bucket": args.bucket or "",
                "interval": args.interval,
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

import os
import time
from datetime import datetime, timezone

import boto3
import pandas as pd
import yfinance as yf


S3_BUCKET = os.environ["S3_BUCKET"]
STOCK_LIST = os.environ["STOCK_LIST"].split(",")

s3 = boto3.client("s3")

# Reuse Ticker objects
TICKERS = {symbol: yf.Ticker(symbol) for symbol in STOCK_LIST}


def log(msg: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] {msg}", flush=True)


def get_val(info: dict, *keys):
    """
    Safely get the first existing key from a dict, or None.
    This handles differences like lastPrice vs last_price vs regularMarketPrice.
    """
    for key in keys:
        if key in info and info[key] is not None:
            return info[key]
    return None


def load_metadata() -> dict[str, dict]:
    """
    Load relatively static metadata once at startup.
    """
    meta: dict[str, dict] = {}
    for symbol, ticker in TICKERS.items():
        try:
            info = ticker.info or {}
        except Exception as e:
            log(f"Error loading metadata for {symbol}: {e}")
            info = {}

        meta[symbol] = {
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "short_name": info.get("shortName"),
        }

    return meta


METADATA = load_metadata()


def fetch_prices() -> list[dict]:
    """
    Fetch latest quote data for all symbols in STOCK_LIST.
    Adds extra fields: volume, open, high, low, previous_close, exchange, currency.
    """
    rows: list[dict] = []
    ts = datetime.now(timezone.utc).isoformat()

    for symbol, ticker in TICKERS.items():
        try:
            finfo = dict(getattr(ticker, "fast_info", {}) or {})

            price = get_val(finfo, "lastPrice", "last_price", "regularMarketPrice")
            if price is None:
                # If we can't get a price, skip this row
                log(f"Price missing for {symbol}, skipping this tick")
                continue

            volume = get_val(
                finfo,
                "lastVolume",
                "last_volume",
                "regularMarketVolume",
                "volume",
            )
            open_price = get_val(finfo, "open", "regularMarketOpen")
            day_high = get_val(
                finfo,
                "dayHigh",
                "day_high",
                "regularMarketDayHigh",
            )
            day_low = get_val(
                finfo,
                "dayLow",
                "day_low",
                "regularMarketDayLow",
            )
            prev_close = get_val(
                finfo,
                "previousClose",
                "previous_close",
                "regularMarketPreviousClose",
            )

            meta = METADATA.get(symbol, {})
            exchange = meta.get("exchange")
            currency = meta.get("currency")
            short_name = meta.get("short_name")

            rows.append(
                {
                    "symbol": symbol,
                    "timestamp": ts,
                    "price": float(price),

                    # dynamic quote fields
                    "volume": volume,
                    "open": open_price,
                    "day_high": day_high,
                    "day_low": day_low,
                    "previous_close": prev_close,

                    # static metadata
                    "exchange": exchange,
                    "currency": currency,
                    "short_name": short_name,
                    "source": "yfinance",
                }
            )
        except Exception as e:
            log(f"Error fetching {symbol}: {e}")

    return rows


def flush_buffer(buffer: list[dict]) -> None:
    if not buffer:
        return

    df = pd.DataFrame(buffer)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")

    key = f"day={date_str}/stocks-{time_str}.parquet"

    tmp_path = "/tmp/data.parquet"
    df.to_parquet(tmp_path)
    s3.upload_file(tmp_path, S3_BUCKET, key)

    log(f"Flushed {len(buffer)} records to s3://{S3_BUCKET}/{key}")


def main() -> None:
    log(f"Starting worker. Bucket={S3_BUCKET}, Stocks={STOCK_LIST}")
    log(f"Loaded metadata: {METADATA}")

    buffer: list[dict] = []
    last_flush = time.time()
    flush_interval_seconds = 10
    poll_interval_seconds = 1

    while True:
        rows = fetch_prices()
        buffer.extend(rows)

        now = time.time()
        if now - last_flush >= flush_interval_seconds:
            flush_buffer(buffer)
            buffer.clear()
            last_flush = now

        time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    main()

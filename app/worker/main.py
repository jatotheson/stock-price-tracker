import os
import time
from datetime import datetime, timezone

import boto3
import pandas as pd
import yfinance as yf


S3_BUCKET = os.environ["S3_BUCKET"]
STOCK_LIST = os.environ["STOCK_LIST"].split(",")

s3 = boto3.client("s3")


def log(msg: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] {msg}", flush=True)


def fetch_prices() -> list[dict]:
    """Fetch latest prices for all symbols in STOCK_LIST."""
    rows: list[dict] = []
    ts = datetime.now(timezone.utc).isoformat()

    for symbol in STOCK_LIST:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = float(f"{info['lastPrice']:.2f}")
            rows.append(
                {
                    "symbol": symbol,
                    "price": price,
                    "timestamp": ts,
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
    date_str = now.strftime("%Y/%m/%d")
    time_str = now.strftime("%H%M%S")
    key = f"{date_str}/stocks-{time_str}.parquet"

    tmp_path = "/tmp/data.parquet"
    df.to_parquet(tmp_path)
    s3.upload_file(tmp_path, S3_BUCKET, key)

    log(f"Flushed {len(buffer)} records to s3://{S3_BUCKET}/{key}")


def main() -> None:
    log(f"Starting worker. Bucket={S3_BUCKET}, Stocks={STOCK_LIST}")

    buffer: list[dict] = []
    last_flush = time.time()
    flush_interval_seconds = 30
    poll_interval_seconds = 3

    while True:
        time.sleep(poll_interval_seconds)

        rows = fetch_prices()
        buffer.extend(rows)

        now = time.time()
        if now - last_flush >= flush_interval_seconds - 1:
            flush_buffer(buffer)
            buffer.clear()
            last_flush = now


if __name__ == "__main__":
    main()

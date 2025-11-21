import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3
import pandas as pd
import yfinance as yf


S3_BUCKET = os.environ["S3_BUCKET"]
STOCK_LIST = [s.strip() for s in os.environ["STOCK_LIST"].split(",") if s.strip()]
EASTERN_TZ = ZoneInfo("America/New_York")

# Optional: hot store in DynamoDB
DDB_INTRADAY_TABLE = os.environ.get("DDB_INTRADAY_TABLE")
INTRADAY_TTL_DAYS = int(os.environ.get("INTRADAY_TTL_DAYS", "60"))

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb") if DDB_INTRADAY_TABLE else None
intraday_table = dynamodb.Table(DDB_INTRADAY_TABLE) if dynamodb else None

# Reuse Ticker objects
TICKERS = {symbol: yf.Ticker(symbol) for symbol in STOCK_LIST}


def log(msg: str) -> None:
    now = datetime.now(EASTERN_TZ).isoformat()
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
    ts = datetime.now(EASTERN_TZ).isoformat()

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


############################
# DynamoDB minute aggregation
############################

@dataclass
class MinuteState:
    minute_start: datetime  # tz-aware (America/New_York)
    last_price: float


# One state per symbol
MINUTE_STATE: dict[str, MinuteState] = {}


def floor_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def write_minute_to_dynamodb(symbol: str, state: MinuteState) -> None:
    if intraday_table is None:
        return

    # minute_start is Eastern; timestamp() gives epoch seconds (UTC-based)
    ts_epoch = int(state.minute_start.timestamp())
    ttl_epoch = int((state.minute_start + timedelta(days=INTRADAY_TTL_DAYS)).timestamp())

    item = {
        "symbol": symbol,
        "ts": ts_epoch,
        "price": state.last_price,
        "ttl": ttl_epoch,
    }

    try:
        intraday_table.put_item(Item=item)
        log(f"DDB minute write: {item}")
    except Exception as e:
        log(f"Error writing to DynamoDB for {symbol}: {e}")


def update_intraday_cache(rows: list[dict]) -> None:
    """
    Update per-symbol minute state and flush previous minute to DynamoDB
    when we cross minute boundary.
    We store exactly one row per minute per symbol, using the last price
    observed in that minute.
    """
    for row in rows:
        symbol = row["symbol"]
        price = row["price"]
        ts_str = row["timestamp"]
        ts = datetime.fromisoformat(ts_str)  # already Eastern

        minute_start = floor_to_minute(ts)

        state = MINUTE_STATE.get(symbol)

        if state is None:
            # First time we see this symbol
            MINUTE_STATE[symbol] = MinuteState(
                minute_start=minute_start,
                last_price=price,
            )
        else:
            if minute_start == state.minute_start:
                # Still within the same minute: update last_price
                state.last_price = price
            else:
                # Minute changed: flush previous minute, start new one
                write_minute_to_dynamodb(symbol, state)
                MINUTE_STATE[symbol] = MinuteState(
                    minute_start=minute_start,
                    last_price=price,
                )


############################
# S3 flush (unchanged)
############################

def flush_buffer(buffer: list[dict]) -> None:
    if not buffer:
        return

    df = pd.DataFrame(buffer)
    log(f"Flushing {len(buffer)} rows with columns: {list(df.columns)}")

    now = datetime.now(EASTERN_TZ)
    date_str = now.strftime("year=%Y/month=%m/day=%d")
    time_str = now.strftime("%H-%M-%S")

    key = f"{date_str}/stocks-{time_str}.parquet"

    tmp_path = "/tmp/data.parquet"
    df.to_parquet(
        tmp_path,
        compression="snappy",
        index=False,
    )
    s3.upload_file(tmp_path, S3_BUCKET, key)

    log(f"Flushed {len(buffer)} records to s3://{S3_BUCKET}/{key}")


def main() -> None:
    log(f"Starting worker. Bucket={S3_BUCKET}, Stocks={STOCK_LIST}, "
        f"DDB_INTRADAY_TABLE={DDB_INTRADAY_TABLE}")
    log(f"Loaded metadata: {METADATA}")

    buffer: list[dict] = []
    last_flush = time.time()
    flush_interval_seconds = 60
    poll_interval_seconds = 3

    while True:
        try:
            rows = fetch_prices()
            buffer.extend(rows)

            # Update DynamoDB minute cache
            update_intraday_cache(rows)

            now = time.time()
            if now - last_flush >= flush_interval_seconds:
                flush_buffer(buffer)
                buffer.clear()
                last_flush = now
        except Exception as e:
            log(f"Top-level error in main loop: {e}")
            time.sleep(poll_interval_seconds)
        finally:
            time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    main()

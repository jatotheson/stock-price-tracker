import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3
import pandas as pd


s3 = boto3.client("s3")

S3_BUCKET = os.environ["S3_BUCKET"]
EASTERN_TZ = ZoneInfo("America/New_York")


def log(msg: str) -> None:
    now = datetime.now(EASTERN_TZ).isoformat()
    print(f"[{now}] {msg}", flush=True)


def parse_range(range_str: str):
    """
    Map range string to (start_dt, end_dt, pandas_freq).
    All in America/New_York time.
    """
    now = datetime.now(EASTERN_TZ)

    if range_str == "1D":
        start = now - timedelta(days=1)
        freq = "1T"   # 1 minute
    elif range_str == "1W":
        start = now - timedelta(days=7)
        freq = "30T"  # 30 minutes
    elif range_str == "1M":
        start = now - timedelta(days=30)
        freq = "1H"   # 1 hour
    else:
        raise ValueError("Unsupported range")

    return start, now, freq


def list_keys_for_window(start_dt: datetime, end_dt: datetime):
    """
    Given a time window, return the S3 object keys to read, based on
    your partition scheme: year=YYYY/month=MM/day=DD/stocks-...parquet
    """
    keys: list[str] = []
    # Start at midnight of the start day
    current = datetime(
        year=start_dt.year,
        month=start_dt.month,
        day=start_dt.day,
        tzinfo=start_dt.tzinfo,
    )

    while current <= end_dt:
        prefix = current.strftime("year=%Y/month=%m/day=%d/")
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
        for obj in resp.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                keys.append(obj["Key"])
        current += timedelta(days=1)

    return keys


def load_data(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Load Parquet files for the window, filter by symbol + time range.
    """
    keys = list_keys_for_window(start_dt, end_dt)
    log(f"Found {len(keys)} parquet files for window {start_dt} to {end_dt}")

    if not keys:
        return pd.DataFrame()

    frames = []
    for key in keys:
        try:
            tmp_path = f"/tmp/{key.replace('/', '_')}"
            s3.download_file(S3_BUCKET, key, tmp_path)
            df = pd.read_parquet(tmp_path)

            # Filter by symbol early
            df = df[df["symbol"] == symbol]
            if df.empty:
                continue

            # Ensure timestamp is datetime with tz
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            frames.append(df)
        except Exception as e:
            log(f"Error reading {key}: {e}")

    if not frames:
        return pd.DataFrame()

    data = pd.concat(frames, ignore_index=True)

    # Filter by time window
    mask = (data["timestamp"] >= start_dt) & (data["timestamp"] <= end_dt)
    data = data.loc[mask]

    # Sort by time
    data = data.sort_values("timestamp")

    return data


def build_timeseries(data: pd.DataFrame, freq: str):
    """
    Resample to the given frequency, taking the last price in each bucket.
    Returns a list of { t, price } points.
    """
    if data.empty:
        return []

    data = data.set_index("timestamp")
    resampled = data["price"].resample(freq).last().dropna()

    points = [
        {"t": ts.isoformat(), "price": float(price)}
        for ts, price in resampled.items()
    ]

    return points


def handler(event, context):
    log(f"Incoming event: {json.dumps(event)}")

    qs = event.get("queryStringParameters") or {}
    symbol = qs.get("symbol")
    range_str = qs.get("range", "1D")

    if not symbol:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "symbol is required"}),
        }

    try:
        start_dt, end_dt, freq = parse_range(range_str)
    except ValueError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "range must be one of 1D, 1W, 1M"}),
        }

    data = load_data(symbol, start_dt, end_dt)
    points = build_timeseries(data, freq)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "symbol": symbol,
                "range": range_str,
                "points": points,
            }
        ),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # allow website
        },
    }

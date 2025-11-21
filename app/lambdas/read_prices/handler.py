import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key


EASTERN_TZ = ZoneInfo("America/New_York")

DDB_INTRADAY_TABLE = os.environ["DDB_INTRADAY_TABLE"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DDB_INTRADAY_TABLE)


def log(msg: str) -> None:
    now = datetime.now(EASTERN_TZ).isoformat()
    print(f"[{now}] {msg}", flush=True)


def parse_range(range_str: str):
    """
    Map range string to (start_dt, end_dt, bucket_seconds) in Eastern time.
    bucket_seconds controls how we aggregate points for 1W / 1M.
    """
    now = datetime.now(EASTERN_TZ)

    if range_str == "1D":
        start = now - timedelta(days=1)
        bucket_seconds = 60          # 1 minute
    elif range_str == "1W":
        start = now - timedelta(days=7)
        bucket_seconds = 30 * 60     # 30 minutes
    elif range_str == "1M":
        start = now - timedelta(days=30)
        bucket_seconds = 60 * 60     # 1 hour
    else:
        raise ValueError("Unsupported range")

    log(f"parse_range: range={range_str}, start={start}, end={now}, bucket_seconds={bucket_seconds}")
    return start, now, bucket_seconds


def query_dynamodb(symbol: str, start_dt: datetime, end_dt: datetime):
    """
    Query DynamoDB for all minute points for (symbol, ts between start/end).
    """
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    log(f"query_dynamodb: symbol={symbol}, start_ts={start_ts}, end_ts={end_ts}")

    items = []
    exclusive_start_key = None

    while True:
        if exclusive_start_key:
            resp = table.query(
                KeyConditionExpression=Key("symbol").eq(symbol) & Key("ts").between(start_ts, end_ts),
                ExclusiveStartKey=exclusive_start_key,
                ScanIndexForward=True,
            )
        else:
            resp = table.query(
                KeyConditionExpression=Key("symbol").eq(symbol) & Key("ts").between(start_ts, end_ts),
                ScanIndexForward=True,
            )

        batch = resp.get("Items", [])
        items.extend(batch)

        exclusive_start_key = resp.get("LastEvaluatedKey")
        if not exclusive_start_key:
            break

    log(f"query_dynamodb: got {len(items)} items for symbol={symbol}")
    return items


def build_points(items, bucket_seconds: int):
    """
    Convert raw minute items into aggregated points.
    For 1D: bucket_seconds = 60 (1 minute) -> essentially one point per minute.
    For 1W: bucket_seconds = 1800 (30 min).
    For 1M: bucket_seconds = 3600 (1 hour).
    We use the last price seen in each bucket.
    """
    if not items:
        log("build_points: no items, returning empty list")
        return []

    # Sort by ts ascending
    items = sorted(items, key=lambda x: x["ts"])

    buckets = {}

    for item in items:
        ts = int(item["ts"])
        price = float(item.get("price") or item.get("close"))

        # Align timestamp to bucket boundary (e.g. minute, 30-min, hour)
        bucket_start_ts = ts - (ts % bucket_seconds)

        # Since items are sorted ascending, later writes overwrite earlier => last price wins
        buckets[bucket_start_ts] = price

    log(f"build_points: {len(items)} raw items -> {len(buckets)} buckets")

    points = [
        {
            "t": datetime.fromtimestamp(bucket_ts, EASTERN_TZ).isoformat(),
            "price": price,
        }
        for bucket_ts, price in sorted(buckets.items())
    ]

    return points


def handler(event, context):
    log(f"Incoming event: {json.dumps(event)}")

    qs = event.get("queryStringParameters") or {}
    symbol = qs.get("symbol")
    range_str = qs.get("range", "1D")

    if not symbol:
        log("handler: missing symbol parameter")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "symbol is required"}),
        }

    try:
        start_dt, end_dt, bucket_seconds = parse_range(range_str)
    except ValueError:
        log(f"handler: invalid range={range_str}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "range must be one of 1D, 1W, 1M"}),
        }

    items = query_dynamodb(symbol, start_dt, end_dt)
    points = build_points(items, bucket_seconds)
    log(f"handler: returning {len(points)} points for symbol={symbol}, range={range_str}")

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
            "Access-Control-Allow-Origin": "*",
        },
    }

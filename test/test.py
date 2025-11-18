import time


import yfinance as yf
import threading
import json
import csv
import pandas as pd



df = pd.read_parquet("test/stocks-194207.parquet")
print(df.head())
print(df.columns)

'''

VERBOSE_PRICE_LOGS = False
OUTPUT_FILE = "sample.csv"
FUNDAMENTALS_TTL = 60 * 60  # 1 hour


stock_symbols = [
    "AAPL",
    "NVDA",
    "TSLA",
    "NFLX",
    "META",
    "MSFT",
    "GOOG",
    "AMZN",
    "ORCL",
    "AVGO"
]

# latest data we've seen from the socket for each symbol
latest_messages = {}
fundamentals_cache = {}
lock = threading.Lock()



ticker_symbol = "NVDA"
ticker = yf.Ticker(ticker_symbol)

info = ticker.info
print(info)

fast_info = ticker.fast_info
print(fast_info)
curr_price = fast_info.last_price
curr_volume = fast_info.last_volume
print(f"Current Price for {ticker_symbol}: {curr_price}")
print(f"Current Volume for {ticker_symbol}: {curr_volume}")
print('\n\n\n\n')

for key in fast_info:
    print(f'{key}:\t{fast_info[key]}')



def handler(message: dict):
    """
    Called on every WebSocket update.
    We store the latest message per symbol.
    """
    # Yahoo's websocket messages usually have an id/symbol field - we use either.
    symbol = message.get("id") or message.get("symbol")
    if symbol is None:
        return

    with lock:
        latest_messages[symbol] = message


# === FUNDAMENTALS FETCHER (USING yf.Ticker().info) ===
def get_fundamentals(symbol: str) -> dict:
    """
    Fetch verbose info for a symbol using yfinance, with simple caching.
    We only refresh once per FUNDAMENTALS_TTL seconds.
    """
    now = time.time()
    cached = fundamentals_cache.get(symbol)

    if cached and now - cached["_fetched_at"] < FUNDAMENTALS_TTL:
        return cached

    info = yf.Ticker(symbol).info

    # Pick only the fields you actually care about for your bot
    selected = {
        "symbol": info.get("symbol", symbol),
        "longName": info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "marketCap": info.get("marketCap"),
        "trailingPE": info.get("trailingPE"),
        "forwardPE": info.get("forwardPE"),
        "beta": info.get("beta"),
        "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
        "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        "dividendYield": info.get("dividendYield"),
        "averageVolume": info.get("averageVolume"),
        "_fetched_at": now,
    }

    fundamentals_cache[symbol] = selected
    return selected



def fundamentals_refresher():
    """
    Optional background thread to keep fundamentals reasonably fresh.
    Runs get_fundamentals(symbol) periodically for each symbol.
    """
    while True:
        for sym in stock_symbols:
            try:
                get_fundamentals(sym)
            except Exception as e:
                print(f"[fundamentals] error fetching {sym}: {e}")
        time.sleep(FUNDAMENTALS_TTL)


# === SAMPLER: EVERY 3 SECONDS ===
def sampler():
    """
    Every 3 seconds, read the latest message per symbol and
    write a normalized row to CSV.
    """

    with open(OUTPUT_FILE, mode="w", newline="") as f:
        writer = csv.writer(f)
        # We store both our ingest timestamp and the source timestamp
        writer.writerow(
            [
                "ingest_ts_ms",
                "source_ts_ms",
                "symbol",
                "price",
                "day_volume",
                "exchange",
            ]
        )

        while True:
            time.sleep(3)

            with lock:
                snapshot = {s: latest_messages.get(s) for s in stock_symbols}

            print("\n=== Snapshot every 3 seconds ===")
            ingest_ts_ms = int(time.time() * 1000)

            for symbol, msg in snapshot.items():
                if not msg:
                    print(f"{symbol}: no data yet")
                    continue

                # Normalize fields from your websocket message
                price = msg.get("price")
                volume_str = msg.get("day_volume")
                exchange = msg.get("exchange")
                source_ts_raw = msg.get("time")  # string with ms since epoch

                # Convert types
                try:
                    volume = int(volume_str) if volume_str is not None else None
                except ValueError:
                    volume = None

                try:
                    source_ts_ms = int(source_ts_raw) if source_ts_raw is not None else None
                except ValueError:
                    source_ts_ms = None

                # Write to CSV (this is the lightweight tick history)
                writer.writerow(
                    [ingest_ts_ms, source_ts_ms, symbol, price, volume, exchange]
                )

                if VERBOSE_PRICE_LOGS:
                    print(
                        f"{symbol}: price={price}, volume={volume}, "
                        f"exchange={exchange}, source_ts={source_ts_ms}"
                    )
                else:
                    print(f"{symbol}: {price}")

            f.flush()



if __name__ == "__main__":
    # Start the 3-second sampler
    sampler_thread = threading.Thread(target=sampler, daemon=True)
    sampler_thread.start()

    # Optional: start fundamentals refresher in background
    fundamentals_thread = threading.Thread(
        target=fundamentals_refresher, daemon=True
    )
    fundamentals_thread.start()

    # Main thread: keep the WebSocket open
    with yf.WebSocket() as ws:
        ws.subscribe(stock_symbols)
        ws.listen(handler)


'''
import time


import yfinance as yf
import threading


VERBOSE_PRICE_LOGS = False

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

# latest data we’ve seen from the socket for each symbol
latest_messages = {}
lock = threading.Lock()


def handler(message: dict):
    """
    Called on every WebSocket update.
    We store the latest message per symbol.
    """
    # Yahoo's websocket messages usually have an id/symbol field – we use either.
    symbol = message.get("id") or message.get("symbol")
    if symbol is None:
        return

    with lock:
        latest_messages[symbol] = message


def sampler():
    """
    Every 3 seconds, read the latest prices we've seen so far
    and print them once.
    """
    while True:
        time.sleep(3)

        with lock:
            snapshot = {s: latest_messages.get(s) for s in stock_symbols}

        print("\n=== Snapshot every 3 seconds ===")
        for symbol, msg in snapshot.items():
            if not msg:
                print(f"{symbol}: no data yet")
                continue

            # Try to pull a price-like field; fall back to printing the whole message
            price = msg.get("price") or msg.get("regularMarketPrice")
            if price is not None:
                if VERBOSE_PRICE_LOGS:
                    print(f"{symbol}: {price}  (raw: {msg})")
                else:
                    print(f"{symbol}: {price}")
            else:
                print(f"{symbol}: (no explicit price field) raw={msg}")


# Start the sampler in the background
thread = threading.Thread(target=sampler, daemon=True)
thread.start()

# Main thread: keep the WebSocket connection open and updating `latest_messages`
with yf.WebSocket() as ws:
    ws.subscribe(stock_symbols)
    ws.listen(handler)



'''
from datetime import datetime

while True:
    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(current_time_str)

    for stock_symbol in stock_symbols: 
        ticker = yf.Ticker(stock_symbol)
        price = str(ticker.info['regularMarketPrice'])
        print(f'{stock_symbol}:\t{price}')

    # tickers = yf.Tickers(' '.join(stock_symbols))

    print('\n\n')
    time.sleep(5)
'''

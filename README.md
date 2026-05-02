
# stock-price-tracker

Side project to track and save stock price in real time.

## commands

### on

curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"action": "on"}' \
  "<https://hunf064i32.execute-api.us-east-1.amazonaws.com/worker>"

### off

curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"action": "off"}' \
  "<https://hunf064i32.execute-api.us-east-1.amazonaws.com/worker>"

### dynamodb stock price

curl "<https://hunf064i32.execute-api.us-east-1.amazonaws.com/prices?symbol=AAPL&range=1D>"

### download daily history parquet files from s3

aws s3 sync s3://stock-tracker-data-dev/daily_history downloaded_stock_data/daily_history --only-show-errors

### generate interactive html graph

venv/bin/python -B scripts/build_stock_price_chart.py


# stock-price-tracker

Side project to download daily 1-minute stock price history after market close.

## tracked stocks

The tracked stock universe is defined in `config/tracked_stocks.csv`. Add,
disable, or edit symbols there; the worker reads that file by default locally
and in ECS.

## commands

### run daily history locally

S3_BUCKET=stock-tracker-data-dev \
venv/bin/python -B app/worker/daily_history.py

For a one-off local run that does not change the tracked stock config:

venv/bin/python -B app/worker/daily_history.py --dry-run --symbols AAPL,MSFT

### download daily history parquet files from s3

aws s3 sync s3://stock-tracker-data-dev/daily_history downloaded_stock_data/daily_history --only-show-errors

### generate interactive html graph

venv/bin/python -B scripts/build_stock_price_chart.py

## notifications

The daily history ECS task publishes SNS messages when the script starts, finishes,
finishes with no data, or fails. Email subscriptions must be confirmed from the
AWS confirmation email.

SMS delivery to US phone numbers also requires an AWS End User Messaging SMS
origination identity in the same region. Without one, SNS accepts the topic
publish but SMS delivery fails with `No origination entities available to send`.
Request a toll-free number or complete 10DLC setup in AWS End User Messaging SMS,
then verify the recipient phone number if the account is still in the SNS SMS
sandbox.

## archive

The original market-hours live ingestion system has been archived under
`archives/original-live-ingestion`. That archive contains the old ECS service
worker, Lambda/API handlers, DynamoDB table Terraform, and on/off schedule
snippets. The active infrastructure keeps only the resources needed by the daily
history ECS task.

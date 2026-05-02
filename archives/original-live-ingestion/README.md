# Original live ingestion archive

Archived on 2026-05-02 when the project moved to the post-close daily history
job.

This folder preserves the original stock-market-hours system that polled
yfinance during the trading day, wrote tick batches to S3, cached minute prices
in DynamoDB, and exposed API Gateway endpoints to switch the ECS service on/off
or read recent DynamoDB prices.

The active project now keeps only the shared pieces needed by the daily history
job: the stock data S3 bucket, ECR repository, ECS cluster/task definition,
networking, CloudWatch logs, SNS notifications, and the 17:30 ET daily schedule.

Archived old-only resources:

- `aws_ecs_service.worker`
- `aws_scheduler_schedule.worker_on`
- `aws_scheduler_schedule.worker_off`
- `aws_lambda_function.worker_switch`
- `aws_lambda_function.read_prices`
- `aws_apigatewayv2_api.worker_api` and routes/integrations/stage
- `aws_dynamodb_table.intraday`
- IAM policies and Lambda permissions used only by those resources

These files are outside the active `infra/` directory, so Terraform will not
load them during normal infrastructure runs.

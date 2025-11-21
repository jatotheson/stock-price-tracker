############################
# Package Lambda (read prices) from local code
############################

data "archive_file" "read_prices_lambda_zip" {
    type        = "zip"
    source_dir  = "${path.module}/../app/lambdas/read_prices"
    output_path = "${path.module}/../app/lambdas/read_prices.zip"
}



############################
# IAM role for read-prices Lambda
############################

resource "aws_iam_role" "lambda_read_role" {
    name = "${var.project_name}-lambda-read-role-${var.env}"

    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Principal = {
                    Service = "lambda.amazonaws.com"
                }
                Action = "sts:AssumeRole"
            }
        ]
    })

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

resource "aws_iam_role_policy" "lambda_read_policy" {
    name = "${var.project_name}-lambda-read-policy-${var.env}"
    role = aws_iam_role.lambda_read_role.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            # CloudWatch Logs
            {
                Effect = "Allow"
                Action = [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ]
                Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
            },
            # Read access to stock data bucket
            {
                Effect = "Allow"
                Action = [
                    "s3:GetObject",
                    "s3:ListBucket"
                ]
                Resource = [
                    aws_s3_bucket.stock_data.arn,
                    "${aws_s3_bucket.stock_data.arn}/*"
                ]
            }
        ]
    })
}



############################
# CloudWatch Logs for read API
############################

resource "aws_cloudwatch_log_group" "read_prices" {
    name              = "/aws/lambda/${var.project_name}-read-prices-${var.env}"
    retention_in_days = 7

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}



############################
# Lambda function: read prices
############################

resource "aws_lambda_function" "read_prices" {
    function_name = "${var.project_name}-read-prices-${var.env}"
    role          = aws_iam_role.lambda_read_role.arn

    filename         = data.archive_file.read_prices_lambda_zip.output_path
    source_code_hash = data.archive_file.read_prices_lambda_zip.output_base64sha256

    handler = "handler.handler"
    runtime = "python3.11"
    timeout = 30
    memory_size = 512

    environment {
        variables = {
            S3_BUCKET = aws_s3_bucket.stock_data.bucket
        }
    }

    tags = {
        Project = var.project_name
        Env     = var.env
    }

    depends_on = [
        aws_cloudwatch_log_group.read_prices
    ]
}



############################
# API Gateway integration for read prices
############################

resource "aws_apigatewayv2_integration" "read_prices" {
    api_id           = aws_apigatewayv2_api.worker.id
    integration_type = "AWS_PROXY"
    integration_uri  = aws_lambda_function.read_prices.arn
    integration_method = "POST"
    payload_format_version = "2.0"
}



# GET https://hunf064i32.execute-api.us-east-1.amazonaws.com/prices?symbol=AAPL&range=1D
resource "aws_apigatewayv2_route" "read_prices" {
    api_id    = aws_apigatewayv2_api.worker.id
    route_key = "GET /prices"

    target = "integrations/${aws_apigatewayv2_integration.read_prices.id}"
}



resource "aws_lambda_permission" "apigw_invoke_read_prices" {
    statement_id  = "AllowAPIGwInvokeReadPrices"
    action        = "lambda:InvokeFunction"
    function_name = aws_lambda_function.read_prices.arn
    principal     = "apigateway.amazonaws.com"
    source_arn    = "${aws_apigatewayv2_api.worker.execution_arn}/*/*"
}

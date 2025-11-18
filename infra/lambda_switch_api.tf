############################
# Package Lambda from local code
############################

data "archive_file" "switch_lambda_zip" {
    type        = "zip"
    source_dir  = "${path.module}/../app/lambdas/switch"
    output_path = "${path.module}/../app/lambdas/switch.zip"
}

############################
# IAM role for Lambda
############################

data "aws_iam_policy_document" "lambda_assume" {
    statement {
        actions = ["sts:AssumeRole"]

        principals {
            type        = "Service"
            identifiers = ["lambda.amazonaws.com"]
        }
    }
}

resource "aws_iam_role" "lambda_switch_role" {
    name               = "${var.project_name}-lambda-switch-role-${var.env}"
    assume_role_policy = data.aws_iam_policy_document.lambda_assume.json

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

# Allow Lambda to write logs + update ECS service
resource "aws_iam_role_policy" "lambda_switch_policy" {
    name = "${var.project_name}-lambda-switch-policy-${var.env}"
    role = aws_iam_role.lambda_switch_role.id

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
            # ECS update service
            {
                Effect = "Allow"
                Action = [
                    "ecs:UpdateService",
                    "ecs:DescribeServices"
                ]
                Resource = "*"
            },
            # SNS publish for notifications
            {
                Effect = "Allow"
                Action = [
                    "sns:Publish"
                ]
                Resource = aws_sns_topic.worker_notifications.arn
            }
        ]
    })
}

data "aws_caller_identity" "current" {}

############################
# Lambda function
############################

resource "aws_lambda_function" "worker_switch" {
    function_name = "${var.project_name}-worker-switch-${var.env}"
    role          = aws_iam_role.lambda_switch_role.arn
    handler       = "handler.handler"
    runtime       = "python3.11"

    filename         = data.archive_file.switch_lambda_zip.output_path
    source_code_hash = data.archive_file.switch_lambda_zip.output_base64sha256

    timeout = 10

    environment {
        variables = {
            ECS_CLUSTER = aws_ecs_cluster.this.name
            ECS_SERVICE = aws_ecs_service.worker.name
            NOTIFY_TOPIC_ARN  = aws_sns_topic.worker_notifications.arn
        }
    }

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

############################
# API Gateway HTTP API
############################

resource "aws_apigatewayv2_api" "worker_api" {
    name          = "${var.project_name}-api-${var.env}"
    protocol_type = "HTTP"

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

resource "aws_apigatewayv2_integration" "worker_integration" {
    api_id                 = aws_apigatewayv2_api.worker_api.id
    integration_type       = "AWS_PROXY"
    integration_uri        = aws_lambda_function.worker_switch.arn
    integration_method     = "POST"
    payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "worker_route" {
    api_id    = aws_apigatewayv2_api.worker_api.id
    route_key = "POST /worker"
    target    = "integrations/${aws_apigatewayv2_integration.worker_integration.id}"
}

resource "aws_apigatewayv2_stage" "worker_stage" {
    api_id      = aws_apigatewayv2_api.worker_api.id
    name        = "$default"
    auto_deploy = true

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

# Allow API Gateway to invoke Lambda
resource "aws_lambda_permission" "apigw_invoke_switch" {
    statement_id  = "AllowAPIGatewayInvokeSwitch"
    action        = "lambda:InvokeFunction"
    function_name = aws_lambda_function.worker_switch.arn
    principal     = "apigateway.amazonaws.com"

    source_arn = "${aws_apigatewayv2_api.worker_api.execution_arn}/*/*"
}

############################
# Output the API endpoint
############################

output "worker_api_endpoint" {
    value = aws_apigatewayv2_api.worker_api.api_endpoint
}

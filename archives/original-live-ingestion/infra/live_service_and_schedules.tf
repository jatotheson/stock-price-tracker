############################
# Archived old-only Terraform snippets
############################

# These resources were embedded in active Terraform files because the original
# project ran an ECS service during market hours. They are archived here for
# reference only; this file is not loaded by the active Terraform root.

resource "aws_iam_role_policy" "ecs_task_ddb_policy" {
  name = "${var.project_name}-ecs-task-ddb-policy-${var.env}"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:DescribeTable"
        ]
        Resource = aws_dynamodb_table.intraday.arn
      }
    ]
  })
}

resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-worker-service-${var.env}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.worker_sg.id]
  }

  tags = {
    Project = var.project_name
    Env     = var.env
  }
}

resource "aws_iam_role_policy" "scheduler_invoke_lambda" {
  name = "${var.project_name}-scheduler-invoke-lambda-${var.env}"
  role = aws_iam_role.scheduler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.worker_switch.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "worker_on" {
  name = "${var.project_name}-worker-on-${var.env}"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression_timezone = "America/New_York"
  schedule_expression          = "cron(0 9 ? * MON-FRI *)"
  state                        = "DISABLED"

  target {
    arn      = aws_lambda_function.worker_switch.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = jsonencode({ action = "on" })
  }
}

resource "aws_scheduler_schedule" "worker_off" {
  name = "${var.project_name}-worker-off-${var.env}"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression_timezone = "America/New_York"
  schedule_expression          = "cron(30 16 ? * MON-FRI *)"
  state                        = "DISABLED"

  target {
    arn      = aws_lambda_function.worker_switch.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = jsonencode({ action = "off" })
  }
}

resource "aws_lambda_permission" "scheduler_on_invoke" {
  statement_id  = "AllowSchedulerOnInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker_switch.arn
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.worker_on.arn
}

resource "aws_lambda_permission" "scheduler_off_invoke" {
  statement_id  = "AllowSchedulerOffInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker_switch.arn
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.worker_off.arn
}

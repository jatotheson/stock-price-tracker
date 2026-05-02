############################
# IAM role for daily history EventBridge Scheduler
############################

locals {
  daily_history_task_group = "${var.project_name}-daily-history-${var.env}"
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler_role" {
  name               = "${var.project_name}-scheduler-role-${var.env}"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json

  tags = {
    Project = var.project_name
    Env     = var.env
  }
}

resource "aws_iam_role_policy" "scheduler_run_ecs_task" {
  name = "${var.project_name}-scheduler-run-ecs-task-${var.env}"
  role = aws_iam_role.scheduler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask"
        ]
        Resource = aws_ecs_task_definition.worker.arn
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.ecs_task_role.arn
      }
    ]
  })
}

############################
# Daily history fetch: 17:30 ET (Mon-Fri)
############################

resource "aws_scheduler_schedule" "daily_history" {
  name = "${var.project_name}-daily-history-${var.env}"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression_timezone = "America/New_York"
  # 30 17 ? * MON-FRI * => 17:30 Mon-Fri, US Eastern
  schedule_expression = "cron(30 17 ? * MON-FRI *)"

  target {
    arn      = aws_ecs_cluster.this.arn
    role_arn = aws_iam_role.scheduler_role.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.worker.arn
      launch_type         = "FARGATE"
      platform_version    = "LATEST"
      group               = local.daily_history_task_group

      network_configuration {
        assign_public_ip = true
        security_groups  = [aws_security_group.worker_sg.id]
        subnets          = data.aws_subnets.default.ids
      }
    }

    input = jsonencode({
      containerOverrides = [
        {
          name    = "worker"
          command = ["python", "daily_history.py"]
        }
      ]
    })
  }
}

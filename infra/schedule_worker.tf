############################
# IAM role for EventBridge Scheduler
############################

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


############################
# Schedules: ON at 09:00 ET, OFF at 16:30 ET (Mon–Fri)
############################

resource "aws_scheduler_schedule" "worker_on" {
    name = "${var.project_name}-worker-on-${var.env}"

    flexible_time_window {
        mode = "OFF"
    }

    schedule_expression_timezone = "America/New_York"
    # 0 9 ? * MON-FRI *  => 09:00 Mon-Fri, US Eastern
    schedule_expression = "cron(0 9 ? * MON-FRI *)"

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
    # 30 16 ? * MON-FRI *  => 16:30 Mon-Fri, US Eastern
    schedule_expression = "cron(30 16 ? * MON-FRI *)"

    target {
        arn      = aws_lambda_function.worker_switch.arn
        role_arn = aws_iam_role.scheduler_role.arn
        input    = jsonencode({ action = "off" })
    }
}


############################
# Lambda permissions for Scheduler
############################

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

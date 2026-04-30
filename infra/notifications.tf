############################
# SNS Topic for notifications
############################

resource "aws_sns_topic" "worker_notifications" {
  name = "${var.project_name}-worker-notifications-${var.env}"

  tags = {
    Project = var.project_name
    Env     = var.env
  }
}

data "aws_iam_policy_document" "worker_notifications_topic_policy" {
  statement {
    sid = "AllowAccountTopicManagement"

    actions = [
      "SNS:AddPermission",
      "SNS:DeleteTopic",
      "SNS:GetTopicAttributes",
      "SNS:ListSubscriptionsByTopic",
      "SNS:Publish",
      "SNS:Receive",
      "SNS:RemovePermission",
      "SNS:SetTopicAttributes",
      "SNS:Subscribe"
    ]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    resources = [
      aws_sns_topic.worker_notifications.arn
    ]
  }

  statement {
    sid = "AllowDailyHistoryEventBridgePublish"

    actions = [
      "SNS:Publish"
    ]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    resources = [
      aws_sns_topic.worker_notifications.arn
    ]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values = [
        aws_cloudwatch_event_rule.daily_history_running.arn,
        aws_cloudwatch_event_rule.daily_history_stopped.arn
      ]
    }
  }
}

resource "aws_sns_topic_policy" "worker_notifications" {
  arn    = aws_sns_topic.worker_notifications.arn
  policy = data.aws_iam_policy_document.worker_notifications_topic_policy.json
}


############################
# Email subscription 
############################
resource "aws_sns_topic_subscription" "worker_email" {
  topic_arn = aws_sns_topic.worker_notifications.arn
  protocol  = "email"
  endpoint  = var.notify_email

  # Don't let Terraform accidentally delete this and spam me
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_sns_topic_subscription" "worker_sms" {
  count = var.notify_phone_number == "" ? 0 : 1

  topic_arn = aws_sns_topic.worker_notifications.arn
  protocol  = "sms"
  endpoint  = var.notify_phone_number

  lifecycle {
    prevent_destroy = true
  }
}

############################
# Daily history ECS task notifications
############################

resource "aws_cloudwatch_event_rule" "daily_history_running" {
  name        = "${var.project_name}-daily-history-running-${var.env}"
  description = "Notify when the daily stock history ECS task starts running."

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      clusterArn        = [aws_ecs_cluster.this.arn]
      taskDefinitionArn = [aws_ecs_task_definition.worker.arn]
      group             = [local.daily_history_task_group]
      lastStatus        = ["RUNNING"]
    }
  })

  tags = {
    Project = var.project_name
    Env     = var.env
  }
}

resource "aws_cloudwatch_event_target" "daily_history_running_sns" {
  rule      = aws_cloudwatch_event_rule.daily_history_running.name
  target_id = "DailyHistoryRunningSns"
  arn       = aws_sns_topic.worker_notifications.arn

  input_transformer {
    input_paths = {
      taskArn = "$.detail.taskArn"
    }

    input_template = "\"Stock daily history ECS task started. Task: <taskArn>\""
  }
}

resource "aws_cloudwatch_event_rule" "daily_history_stopped" {
  name        = "${var.project_name}-daily-history-stopped-${var.env}"
  description = "Notify when the daily stock history ECS task stops."

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      clusterArn        = [aws_ecs_cluster.this.arn]
      taskDefinitionArn = [aws_ecs_task_definition.worker.arn]
      group             = [local.daily_history_task_group]
      lastStatus        = ["STOPPED"]
    }
  })

  tags = {
    Project = var.project_name
    Env     = var.env
  }
}

resource "aws_cloudwatch_event_target" "daily_history_stopped_sns" {
  rule      = aws_cloudwatch_event_rule.daily_history_stopped.name
  target_id = "DailyHistoryStoppedSns"
  arn       = aws_sns_topic.worker_notifications.arn

  input_transformer {
    input_paths = {
      exitCode      = "$.detail.containers[0].exitCode"
      stoppedReason = "$.detail.stoppedReason"
      taskArn       = "$.detail.taskArn"
    }

    input_template = "\"Stock daily history ECS task stopped. Exit code: <exitCode>. Reason: <stoppedReason>. Task: <taskArn>\""
  }
}

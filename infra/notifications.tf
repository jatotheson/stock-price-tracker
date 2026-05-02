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

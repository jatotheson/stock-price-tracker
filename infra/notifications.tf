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

############################
# Email subscription (optional)
############################

resource "aws_sns_topic_subscription" "worker_email" {
    count = var.notify_email != "" ? 1 : 0

    topic_arn = aws_sns_topic.worker_notifications.arn
    protocol  = "email"
    endpoint  = var.notify_email
}

############################
# SMS subscription (optional)
############################

resource "aws_sns_topic_subscription" "worker_sms" {
    count = var.notify_phone != "" ? 1 : 0

    topic_arn = aws_sns_topic.worker_notifications.arn
    protocol  = "sms"
    endpoint  = var.notify_phone
}

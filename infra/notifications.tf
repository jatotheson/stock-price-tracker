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
    topic_arn = aws_sns_topic.worker_notifications.arn
    protocol  = "email"
    endpoint  = var.notify_email

    # Don't let Terraform accidentally delete this and spam you
    lifecycle {
        prevent_destroy = true
    }
}


############################
# SMS subscription (optional)
############################
resource "aws_sns_topic_subscription" "worker_sms" {
    topic_arn = aws_sns_topic.worker_notifications.arn
    protocol  = "sms"
    endpoint  = var.notify_phone

    # Don't let Terraform accidentally delete this and spam you
    lifecycle {
        prevent_destroy = true
    }
}
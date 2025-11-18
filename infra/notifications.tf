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


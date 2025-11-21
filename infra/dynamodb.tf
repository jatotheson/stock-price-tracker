############################
# DynamoDB table for intraday minute prices
############################

resource "aws_dynamodb_table" "intraday" {
    name         = "${var.project_name}-intraday-${var.env}"
    billing_mode = "PAY_PER_REQUEST"

    hash_key  = "symbol"
    range_key = "ts"

    attribute {
        name = "symbol"
        type = "S"
    }

    attribute {
        name = "ts"
        type = "N"
    }

    ttl {
        attribute_name = "ttl"
        enabled        = true
    }

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

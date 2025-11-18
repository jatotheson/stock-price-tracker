terraform {
    required_version = ">= 1.6.0"

    backend "s3" {
        bucket         = "stock-tracker-bootstrap-tf-state-b38de212"
        key            = "global/terraform.tfstate"
        region         = "us-east-1"
        dynamodb_table = "stock-tracker-bootstrap-tf-lock"
    }

    required_providers {
        aws = {
          source  = "hashicorp/aws"
          version = "~> 5.0"
        }
    }
}

provider "aws" {
    region = var.aws_region
}

# Simple S3 bucket for your actual stock data (NOT the tf state)
resource "aws_s3_bucket" "stock_data" {
    bucket = "${var.project_name}-data-${var.env}"

    tags = {
        Project = var.project_name
        Env     = var.env
        Purpose = "stock-data"
    }
}

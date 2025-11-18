
variable "project_name" {
    type    = string
    default = "stock-tracker"
}

variable "aws_region" {
    type    = string
    default = "us-east-1"
}

variable "env" {
    type    = string
    default = "dev"
}

	
# s3 bucket name: stock-tracker-bootstrap-tf-state-b38de212
# dynamodb table name: stock-tracker-bootstrap-tf-lock



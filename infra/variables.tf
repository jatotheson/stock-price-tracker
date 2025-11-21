
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

variable "notify_email" {
    type    = string
    default = "jason6858@gmail.com"
}

variable "stock_symbols" {
    type = list(string)
    default = [
        "AAPL",
        "NVDA",
        "TSLA",
        "NFLX",
        "META",
        "MSFT",
        "GOOG",
        "AMZN",
        "ORCL",
        "AVGO"
    ]
}



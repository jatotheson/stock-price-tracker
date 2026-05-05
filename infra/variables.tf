
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

variable "notify_phone_number" {
  type        = string
  default     = ""
  description = "Optional E.164 phone number for SNS SMS notifications, e.g. +15551234567."

  validation {
    condition     = var.notify_phone_number == "" || can(regex("^\\+[1-9][0-9]{7,14}$", var.notify_phone_number))
    error_message = "notify_phone_number must be empty or an E.164 phone number like +15551234567."
  }
}

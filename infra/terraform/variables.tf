variable "aws_region" {
  description = "AWS region for the platform."
  type        = string
  default     = "eu-west-3"
}

variable "budget_alert_email" {
  description = "Email notified when the monthly AWS budget threshold is reached."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_alert_email))
    error_message = "Set budget_alert_email to a valid email address."
  }
}

variable "monthly_budget_usd" {
  description = "Monthly cost alert threshold in USD."
  type        = number
  default     = 20
}

variable "api_allowed_cidr" {
  description = "IPv4 CIDR allowed to access the unauthenticated dashboard; use your IP with /32."
  type        = string

  validation {
    condition     = can(cidrhost(var.api_allowed_cidr, 0))
    error_message = "Set api_allowed_cidr to a valid IPv4 CIDR, preferably a single trusted IP with /32."
  }
}

variable "service_desired_count" {
  description = "Number of always-on dashboard tasks."
  type        = number
  default     = 0
}

variable "schedule_enabled" {
  description = "Enable the daily EventBridge pipeline task."
  type        = bool
  default     = false
}

variable "image_tag" {
  description = "Immutable container image tag to deploy."
  type        = string
  default     = "bootstrap"
}

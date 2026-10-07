# Email alerts: a monthly cost budget, and alarms when the demo breaks.
# After the first apply, AWS emails a confirmation link for the alarm topic;
# alarms are only delivered once it is clicked.

variable "alert_email" {
  description = "Where alerts go. Put it in terraform.tfvars."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly AWS spend that triggers budget emails (whole account)."
  type        = number
  default     = 20
}

variable "create_budget" {
  description = "Set to false if the account already has a budget you want to keep using."
  type        = bool
  default     = true
}

resource "aws_sns_topic" "alerts" {
  name = "${var.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- Cost ---

resource "aws_budgets_budget" "monthly" {
  count        = var.create_budget ? 1 : 0
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Half spent, fully spent, and on track to overspend.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# --- Health ---

# Counts the HOMEDOCS_FAILURE lines the agent logs when a request fails
# (Bedrock errors, MCP server unreachable, Cognito problems, warm-up failures).
resource "aws_cloudwatch_log_metric_filter" "agent_failures" {
  name           = "${var.name}-agent-failures"
  log_group_name = aws_cloudwatch_log_group.agent.name
  pattern        = "\"HOMEDOCS_FAILURE\""

  metric_transformation {
    name          = "AgentFailures"
    namespace     = "HomeDocs"
    value         = "1"
    default_value = "0"
  }
}

locals {
  alarm_defaults = {
    period              = 300
    evaluation_periods  = 1
    comparison_operator = "GreaterThanOrEqualToThreshold"
    threshold           = 1
    statistic           = "Sum"
  }
}

resource "aws_cloudwatch_metric_alarm" "agent_failures" {
  alarm_name          = "${var.name}-agent-failures"
  alarm_description   = "A demo request failed. Check the ${aws_cloudwatch_log_group.agent.name} log group for HOMEDOCS_FAILURE."
  namespace           = "HomeDocs"
  metric_name         = "AgentFailures"
  period              = local.alarm_defaults.period
  evaluation_periods  = local.alarm_defaults.evaluation_periods
  comparison_operator = local.alarm_defaults.comparison_operator
  threshold           = local.alarm_defaults.threshold
  statistic           = local.alarm_defaults.statistic
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# Crashes and timeouts inside the Lambda itself.
resource "aws_cloudwatch_metric_alarm" "agent_errors" {
  alarm_name          = "${var.name}-agent-lambda-errors"
  alarm_description   = "The agent Lambda crashed or timed out."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.agent.function_name }
  period              = local.alarm_defaults.period
  evaluation_periods  = local.alarm_defaults.evaluation_periods
  comparison_operator = local.alarm_defaults.comparison_operator
  threshold           = local.alarm_defaults.threshold
  statistic           = local.alarm_defaults.statistic
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# Requests turned away because the account's Lambda concurrency ran out.
resource "aws_cloudwatch_metric_alarm" "agent_throttles" {
  alarm_name          = "${var.name}-agent-lambda-throttles"
  alarm_description   = "The agent Lambda is being throttled."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.agent.function_name }
  period              = local.alarm_defaults.period
  evaluation_periods  = local.alarm_defaults.evaluation_periods
  comparison_operator = local.alarm_defaults.comparison_operator
  threshold           = local.alarm_defaults.threshold
  statistic           = local.alarm_defaults.statistic
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# Unusual traffic: more than 200 agent calls in an hour (the warm-up alone is 12)
# means someone is using the site heavily, which costs Bedrock money.
resource "aws_cloudwatch_metric_alarm" "agent_traffic" {
  alarm_name          = "${var.name}-agent-traffic-spike"
  alarm_description   = "More than 200 agent invocations in an hour."
  namespace           = "AWS/Lambda"
  metric_name         = "Invocations"
  dimensions          = { FunctionName = aws_lambda_function.agent.function_name }
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 200
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

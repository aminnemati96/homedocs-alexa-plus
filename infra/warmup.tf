# Keeps the agent Lambda and its AgentCore MCP session warm so the first visitor
# doesn't wait for two cold starts. Turn off after judging with
#   terraform apply -var keep_warm=false

variable "keep_warm" {
  description = "Ping the agent every 5 minutes to avoid cold starts."
  type        = bool
  default     = true
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "warmup" {
  name               = "${var.name}-warmup-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "warmup" {
  role = aws_iam_role.warmup.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.agent.arn
    }]
  })
}

resource "aws_scheduler_schedule" "warmup" {
  name                = "${var.name}-warmup"
  schedule_expression = "rate(5 minutes)"
  state               = var.keep_warm ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.agent.arn
    role_arn = aws_iam_role.warmup.arn
    # The Lambda Web Adapter forwards this payload to POST /events.
    input = jsonencode({ warmup = random_password.origin_secret.result })

    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}

# The agent API on Lambda (container image with the Lambda Web Adapter),
# exposed through a streaming function URL that only CloudFront should call.

variable "agent_image_tag" {
  description = "Tag of the agent image in ECR. Change it to roll out a new build."
  type        = string
  default     = "v1"
}

variable "demo_passcode" {
  description = "Passcode visitors type on the site. Put it in terraform.tfvars (gitignored)."
  type        = string
  sensitive   = true
}

variable "bedrock_model_id" {
  description = "Chat model (inference profile) the agent uses."
  type        = string
  default     = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
}

resource "aws_ecr_repository" "agent" {
  name                 = "${var.name}-agent"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name
  policy     = aws_ecr_lifecycle_policy.mcp.policy
}

# CloudFront sends this header; the agent rejects requests without it.
resource "random_password" "origin_secret" {
  length  = 40
  special = false
}

resource "aws_secretsmanager_secret" "cognito_client_secret" {
  name                    = "${var.name}/cognito-agent-client-secret"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cognito_client_secret" {
  secret_id     = aws_secretsmanager_secret.cognito_client_secret.id
  secret_string = aws_cognito_user_pool_client.agent.client_secret
}

# --- IAM ---

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "agent_permissions" {
  statement {
    sid     = "ChatModel"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    # A global inference profile can route to the model in any region.
    resources = [
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.bedrock_model_id}",
      "arn:aws:bedrock:*::foundation-model/${trimprefix(var.bedrock_model_id, "global.")}",
      "arn:aws:bedrock:::foundation-model/${trimprefix(var.bedrock_model_id, "global.")}",
    ]
  }
  statement {
    sid       = "Voice"
    actions   = ["polly:SynthesizeSpeech"]
    resources = ["*"]
  }
  statement {
    sid       = "CognitoSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.cognito_client_secret.arn]
  }
}

resource "aws_iam_role" "agent" {
  name               = "${var.name}-agent-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "agent_logs" {
  role       = aws_iam_role.agent.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "agent" {
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent_permissions.json
}

# --- Function ---

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/aws/lambda/${var.name}-agent"
  retention_in_days = 14
}

resource "aws_lambda_function" "agent" {
  function_name = "${var.name}-agent"
  role          = aws_iam_role.agent.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.agent.repository_url}:${var.agent_image_tag}"
  architectures = ["arm64"]
  memory_size   = 1024
  timeout       = 120

  environment {
    variables = {
      MCP_URL                   = "https://bedrock-agentcore.${var.region}.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.mcp.agent_runtime_arn)}/invocations?qualifier=DEFAULT"
      BEDROCK_MODEL_ID          = var.bedrock_model_id
      COGNITO_TOKEN_URL         = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com/oauth2/token"
      COGNITO_CLIENT_ID         = aws_cognito_user_pool_client.agent.id
      COGNITO_SCOPE             = one(aws_cognito_resource_server.mcp.scope_identifiers)
      COGNITO_CLIENT_SECRET_ARN = aws_secretsmanager_secret.cognito_client_secret.arn
      DEMO_PASSCODE             = var.demo_passcode
      ORIGIN_SECRET             = random_password.origin_secret.result
    }
  }

  depends_on = [aws_cloudwatch_log_group.agent, aws_iam_role_policy_attachment.agent_logs]
}

resource "aws_lambda_function_url" "agent" {
  function_name      = aws_lambda_function.agent.function_name
  authorization_type = "NONE" # guarded by the origin secret and the passcode
  invoke_mode        = "RESPONSE_STREAM"
}

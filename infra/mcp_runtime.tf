# The homedocs MCP server, hosted on Amazon Bedrock AgentCore Runtime.
#
# Two-step first deploy (the runtime needs the image to exist):
#   1. terraform apply -target=aws_ecr_repository.mcp
#   2. build and push the image, then terraform apply -var mcp_image_tag=<tag>

variable "mcp_image_tag" {
  description = "Tag of the MCP server image in ECR. Change it to roll out a new build."
  type        = string
  default     = "v1"
}

resource "aws_ecr_repository" "mcp" {
  name                 = "${var.name}-mcp-server"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "mcp" {
  repository = aws_ecr_repository.mcp.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# --- IAM role the runtime assumes ---

data "aws_iam_policy_document" "mcp_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    # Confused-deputy protection: only runtimes in this account.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
    }
  }
}

data "aws_iam_policy_document" "mcp_permissions" {
  statement {
    sid       = "PullImage"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [aws_ecr_repository.mcp.arn]
  }
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "Logs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }
  statement {
    sid       = "Documents"
    actions   = ["dynamodb:Scan", "dynamodb:GetItem", "dynamodb:PutItem"]
    resources = [aws_dynamodb_table.documents.arn]
  }
  statement {
    sid = "Vectors"
    # GetVectors is required for queries that return metadata.
    actions   = ["s3vectors:PutVectors", "s3vectors:QueryVectors", "s3vectors:GetVectors"]
    resources = [aws_s3vectors_index.passages.index_arn]
  }
  statement {
    sid       = "Embeddings"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0"]
  }
}

resource "aws_iam_role" "mcp" {
  name               = "${var.name}-mcp-runtime"
  assume_role_policy = data.aws_iam_policy_document.mcp_assume.json
}

resource "aws_iam_role_policy" "mcp" {
  role   = aws_iam_role.mcp.id
  policy = data.aws_iam_policy_document.mcp_permissions.json
}

# --- The runtime ---

resource "aws_bedrockagentcore_agent_runtime" "mcp" {
  agent_runtime_name = "${var.name}_mcp_server" # letters, digits and underscores only
  description        = "homedocs MCP server: household paperwork tools"
  role_arn           = aws_iam_role.mcp.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.mcp.repository_url}:${var.mcp_image_tag}"
    }
  }

  environment_variables = {
    HOMEDOCS_TABLE         = aws_dynamodb_table.documents.name
    HOMEDOCS_VECTOR_BUCKET = aws_s3vectors_vector_bucket.passages.vector_bucket_name
    HOMEDOCS_VECTOR_INDEX  = aws_s3vectors_index.passages.index_name
  }

  # Only callers holding a Cognito token from our app client get in.
  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/openid-configuration"
      allowed_clients = [aws_cognito_user_pool_client.agent.id]
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "MCP"
  }

  depends_on = [aws_iam_role_policy.mcp]
}

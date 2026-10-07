output "documents_table" {
  value = aws_dynamodb_table.documents.name
}

output "vector_bucket" {
  value = aws_s3vectors_vector_bucket.passages.vector_bucket_name
}

output "vector_index" {
  value = aws_s3vectors_index.passages.index_name
}

output "mcp_image_repository" {
  value = aws_ecr_repository.mcp.repository_url
}

output "mcp_url" {
  description = "Streamable HTTP endpoint of the hosted MCP server."
  value       = "https://bedrock-agentcore.${var.region}.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.mcp.agent_runtime_arn)}/invocations?qualifier=DEFAULT"
}

output "cognito_token_url" {
  value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com/oauth2/token"
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.agent.id
}

output "cognito_client_secret" {
  value     = aws_cognito_user_pool_client.agent.client_secret
  sensitive = true
}

output "cognito_scope" {
  value = one(aws_cognito_resource_server.mcp.scope_identifiers)
}

output "agent_image_repository" {
  value = aws_ecr_repository.agent.repository_url
}

output "web_bucket" {
  value = aws_s3_bucket.web.bucket
}

output "site_url" {
  value = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

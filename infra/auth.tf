# Machine-to-machine sign-in: the agent gets an access token with the OAuth
# client credentials flow and presents it to the AgentCore-hosted MCP server.

resource "aws_cognito_user_pool" "main" {
  name = "${var.name}-users"
}

resource "aws_cognito_user_pool_domain" "main" {
  # Domain prefixes are global across AWS, so include the account id.
  domain       = "${var.name}-${data.aws_caller_identity.current.account_id}"
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_resource_server" "mcp" {
  identifier   = "homedocs"
  name         = "homedocs MCP server"
  user_pool_id = aws_cognito_user_pool.main.id

  scope {
    scope_name        = "mcp"
    scope_description = "Call the homedocs MCP tools"
  }
}

resource "aws_cognito_user_pool_client" "agent" {
  name            = "${var.name}-agent"
  user_pool_id    = aws_cognito_user_pool.main.id
  generate_secret = true

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = aws_cognito_resource_server.mcp.scope_identifiers
  supported_identity_providers         = ["COGNITO"]

  access_token_validity = 60
  token_validity_units {
    access_token = "minutes"
  }
}

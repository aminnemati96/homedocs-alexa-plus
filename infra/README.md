# Infrastructure (Terraform)

| File | What it creates |
| --- | --- |
| `storage.tf` | DynamoDB table for documents, S3 vector bucket and index for passages |
| `auth.tf` | Cognito user pool, domain and app client (client credentials) |
| `mcp_runtime.tf` | ECR repository, IAM role, and the MCP server on Bedrock AgentCore Runtime |

## Deploy the MCP server

First time only, create the image repository:

```
terraform init
terraform apply "-target=aws_ecr_repository.mcp"
```

Build and push the image (ARM64 is required by AgentCore), from PowerShell:

```
$repo = terraform output -raw mcp_image_repository
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $repo.Split("/")[0]
docker buildx build --platform linux/arm64 -t "${repo}:v1" --push ../mcp-server
terraform apply
```

To ship a new build, push it with a new tag and run `terraform apply -var mcp_image_tag=v2`.
Image tags are immutable, so every build needs a new tag.

Note: PowerShell needs quotes around `-chdir=...` and `-target=...` options.

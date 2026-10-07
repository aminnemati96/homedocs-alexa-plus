# Infrastructure (Terraform)

| File | What it creates |
| --- | --- |
| `storage.tf` | DynamoDB table for documents, S3 vector bucket and index for passages |
| `auth.tf` | Cognito user pool, domain and app client (client credentials) |
| `mcp_runtime.tf` | ECR repository, IAM role, and the MCP server on Bedrock AgentCore Runtime |
| `agent.tf` | ECR repository, IAM role, Secrets Manager secret, Lambda function and streaming function URL |
| `web.tf` | Private S3 bucket and CloudFront distribution (`/` to S3, `/api/*` to Lambda) |

Commands below are for PowerShell, which needs quotes around `-chdir=...` and
`-target=...` options. Run them from this folder.

## First deploy

1. Create `terraform.tfvars` (gitignored) with the passcode visitors will type:

   ```
   demo_passcode = "choose-one"
   ```

2. Create the image repositories, log Docker in to ECR, and push both images
   (AgentCore and the Lambda both run ARM64):

   ```
   terraform init
   terraform apply "-target=aws_ecr_repository.mcp" "-target=aws_ecr_repository.agent"
   $mcpRepo = terraform output -raw mcp_image_repository
   $agentRepo = terraform output -raw agent_image_repository
   $registry = $mcpRepo.Split("/")[0]
   docker login --username AWS --password (aws ecr get-login-password --region us-east-1) $registry
   docker buildx build --platform linux/arm64 -t "${mcpRepo}:v1" --push ../mcp-server
   docker buildx build --platform linux/arm64 --provenance=false -t "${agentRepo}:v1" --push ../agent
   ```

3. Create everything else (CloudFront takes several minutes):

   ```
   terraform apply
   ```

4. Load the sample documents into DynamoDB and S3 Vectors:

   ```
   cd ../mcp-server
   $env:HOMEDOCS_STORE = "dynamodb"
   $env:HOMEDOCS_SEARCH = "s3vectors"
   $env:HOMEDOCS_VECTOR_BUCKET = (terraform "-chdir=../infra" output -raw vector_bucket)
   uv run homedocs-ingest
   ```

5. Build and upload the web app:

   ```
   cd ../web
   pnpm build
   aws s3 sync dist "s3://$(terraform "-chdir=../infra" output -raw web_bucket)" --delete
   aws cloudfront create-invalidation --distribution-id (terraform "-chdir=../infra" output -raw distribution_id) --paths "/*"
   terraform "-chdir=../infra" output -raw site_url
   ```

## Updates

Image tags are immutable, so every new build gets a new tag:

```
docker buildx build --platform linux/arm64 -t "${mcpRepo}:v2" --push ../mcp-server
terraform apply -var mcp_image_tag=v2
```

The agent works the same way with `agent_image_tag` (and `--provenance=false`).
For web changes, repeat step 5.

## Tear down

`terraform destroy` removes everything, including stored documents.

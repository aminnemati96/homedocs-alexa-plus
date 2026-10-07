variable "region" {
  description = "AWS region for everything (Bedrock models, AgentCore, storage)."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Prefix for resource names."
  type        = string
  default     = "homedocs"
}

variable "embedding_dimensions" {
  description = "Must match the Titan Text Embeddings V2 setting in mcp-server/embeddings.py."
  type        = number
  default     = 1024
}

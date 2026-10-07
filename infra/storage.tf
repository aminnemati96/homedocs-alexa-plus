# Documents: one item per document, the document JSON in `body`.
resource "aws_dynamodb_table" "documents" {
  name         = "${var.name}-documents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}

# Passage embeddings for semantic search.
resource "aws_s3vectors_vector_bucket" "passages" {
  # Account id keeps the name unique without guessing.
  vector_bucket_name = "${var.name}-vectors-${data.aws_caller_identity.current.account_id}"
  force_destroy      = true
}

resource "aws_s3vectors_index" "passages" {
  index_name         = "passages"
  vector_bucket_name = aws_s3vectors_vector_bucket.passages.vector_bucket_name

  data_type       = "float32"
  dimension       = var.embedding_dimensions
  distance_metric = "cosine"

  # Only document_id is used for filtering; the text fields are just returned.
  metadata_configuration {
    non_filterable_metadata_keys = ["title", "passage"]
  }
}

output "documents_table" {
  value = aws_dynamodb_table.documents.name
}

output "vector_bucket" {
  value = aws_s3vectors_vector_bucket.passages.vector_bucket_name
}

output "vector_index" {
  value = aws_s3vectors_index.passages.index_name
}

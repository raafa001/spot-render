output "bucket_name" {
  description = "Nome do bucket usado como backend remoto"
  value       = aws_s3_bucket.state.bucket
}

output "bucket_arn" {
  description = "ARN completo do bucket do state"
  value       = aws_s3_bucket.state.arn
}

output "kms_key_arn" {
  description = "ARN da KMS Key usada para criptografia do bucket"
  value       = aws_kms_key.state.arn
}

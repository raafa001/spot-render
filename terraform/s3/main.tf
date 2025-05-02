resource "aws_s3_bucket" "renderizacao_source" {
  bucket = "renderizacao-source-bucket" # **MELHORIA: Nome específico para bucket de origem**
  acl    = "private"

  tags = {
    Name        = "renderizacao-source-bucket"
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
    Purpose     = "Source files for rendering" # Indica a finalidade do bucket
  }
}

resource "aws_s3_bucket" "renderizacao_output" {
  bucket = "renderizacao-output-bucket" # **MELHORIA: Nome específico para bucket de saída**
  acl    = "private"

  tags = {
    Name        = "renderizacao-output-bucket"
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
    Purpose     = "Rendered output files" # Indica a finalidade do bucket
  }
}

output "s3_source_bucket_arn" {
  value = aws_s3_bucket.renderizacao_source.arn
}

output "s3_output_bucket_arn" {
  value = aws_s3_bucket.renderizacao_output.arn
}
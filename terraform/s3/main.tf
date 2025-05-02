resource "aws_s3_bucket" "renderizacao_source" {
  bucket = "renderizacao-source-bucket"

  tags = {
    Name        = "renderizacao-source-bucket"
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
    Purpose     = "Source files for rendering"
  }
}

resource "aws_s3_bucket_acl" "renderizacao_source_acl" {
  bucket = aws_s3_bucket.renderizacao_source.id
  acl    = "private"
}

resource "aws_s3_bucket_ownership_controls" "renderizacao_source_ownership" {
  bucket = aws_s3_bucket.renderizacao_source.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket" "renderizacao_output" {
  bucket = "renderizacao-output-bucket"

  tags = {
    Name        = "renderizacao-output-bucket"
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
    Purpose     = "Rendered output files"
  }
}

resource "aws_s3_bucket_acl" "renderizacao_output_acl" {
  bucket = aws_s3_bucket.renderizacao_output.id
  acl    = "private"
}

resource "aws_s3_bucket_ownership_controls" "renderizacao_output_ownership" {
  bucket = aws_s3_bucket.renderizacao_output.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

output "s3_bucket_arn" {
  value = aws_s3_bucket.renderizacao_source.arn
}
resource "aws_s3_bucket" "renderizacao_source" {
  bucket                 = "renderizacao-source-bucket"
  bucket_acl             = "private"
  control_object_ownership = "BucketOwnerEnforced"

  tags = {
    Name        = "renderizacao-source-bucket"
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
    Purpose     = "Source files for rendering"
  }
}

resource "aws_s3_bucket" "renderizacao_output" {
  bucket                 = "renderizacao-output-bucket"
  bucket_acl             = "private"
  control_object_ownership = "BucketOwnerEnforced"

  tags = {
    Name        = "renderizacao-output-bucket"
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
    Purpose     = "Rendered output files"
  }
}

output "s3_bucket_arn" { # **Adicionado output para o ARN do bucket (ambos os buckets terão o mesmo output por simplicidade)**
  value = aws_s3_bucket.renderizacao_source.arn
}

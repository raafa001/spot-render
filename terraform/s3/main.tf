provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "renderizacao" {
  bucket = "renderizacao-bucket"
  acl    = "private"
}

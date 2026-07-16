terraform {
  required_version = ">= 1.6.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.60"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = merge(
      {
        Project   = "spot-render"
        ManagedBy = "terraform"
        Stack     = "state-backend"
      },
      var.tags
    )
  }
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  bucket_arn = "arn:${data.aws_partition.current.partition}:s3:::${var.bucket_name}"
}

resource "aws_kms_key" "state" {
  description             = "Spot Render Terraform state bucket"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowRootAccount"
        Effect = "Allow"
        Principal = {
          AWS = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowS3BucketEncryption"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:DescribeKey",
          "kms:GenerateDataKey*",
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "state" {
  name          = "alias/spot-render-terraform"
  target_key_id = aws_kms_key.state.key_id
}

resource "aws_s3_bucket" "state" {
  bucket              = var.bucket_name
  force_destroy       = false
  object_lock_enabled = true

  tags = merge({
    Name        = var.bucket_name
    Environment = "global"
  }, var.tags)
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.state.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
    # MFA delete não possui API pública para automação.
    # Protegemos operações destrutivas via bucket policy.
  }

  depends_on = [aws_s3_bucket_public_access_block.state]
}

resource "aws_s3_bucket_object_lock_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    default_retention {
      mode = var.object_lock_mode
      days = var.object_lock_default_retention_days
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "noncurrent-transition"
    status = "Enabled"

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

locals {
  mfa_principals = length(var.allow_delete_without_mfa_principals) == 0 ? ["never-match"] : var.allow_delete_without_mfa_principals
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          local.bucket_arn,
          "${local.bucket_arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "RequireMFAForDeletes"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "s3:DeleteObject",
          "s3:DeleteObjectVersion",
          "s3:DeleteObjectTagging",
          "s3:DeleteObjectVersionTagging"
        ]
        Resource = "${local.bucket_arn}/*"
        Condition = {
          StringNotEqualsIfExists = {
            "aws:PrincipalArn" = local.mfa_principals
          }
          Bool = {
            "aws:MultiFactorAuthPresent" = "false"
          }
        }
      }
    ]
  })
}

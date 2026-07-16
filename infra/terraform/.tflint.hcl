config {
  module  = true
  force   = false
  format  = "compact"
}

plugin "aws" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

rule "aws_instance_invalid_type" {
  enabled = true
}

rule "aws_s3_bucket_versioning" {
  enabled = true
}

rule "aws_security_group_ingress_cidr_blocks" {
  enabled = true
}

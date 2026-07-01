# ──────────────────────────────────────────────────────────────────────────────
# Módulo: secrets
# Provisão de AWS Secrets Manager para armazenar:
#   - Credenciais do banco de dados
#   - Credenciais do Redis
#   - API keys e tokens
# ──────────────────────────────────────────────────────────────────────────────

locals {
  tags = {
    Project     = "spot-render"
    Environment = var.environment
    Component   = "secrets"
  }
}

# ─── Secrets para Banco de Dados ──────────────────────────────────────────────

resource "aws_secretsmanager_secret" "database" {
  name        = "${var.prefix}/database/credentials"
  description = "Credenciais do banco de dados Spot Render"

  kms_key_id = var.kms_key_id

  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    engine   = "postgres"
    host     = var.db_host
    port     = 5432
    dbname   = var.db_name
  })

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id

  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    engine   = "postgres"
    host     = var.db_host
    port     = 5432
    dbname   = var.db_name
  })
}

# ─── Secrets para Redis ────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "redis" {
  count       = var.redis_password != null ? 1 : 0
  name        = "${var.prefix}/redis/credentials"
  description = "Credenciais do Redis Spot Render"

  kms_key_id = var.kms_key_id

  secret_string = jsonencode({
    host     = var.redis_host
    port     = 6379
    password = var.redis_password
  })

  tags = local.tags
}

# ─── Secrets para SQS ─────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "sqs" {
  name        = "${var.prefix}/sqs/credentials"
  description = "Credenciais de acesso ao SQS Spot Render"

  kms_key_id = var.kms_key_id

  secret_string = jsonencode({
    queue_url = var.sqs_queue_url
    dlq_url   = var.sqs_dlq_url
  })

  tags = local.tags
}

# ─── Policy para，允许API读取secrets ─────────────────────────────────────────

data "aws_iam_policy_document" "secret_read" {
  statement {
    sid    = "AllowAPIRoleReadSecrets"
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]

    resources = [
      aws_secretsmanager_secret.database.arn,
      aws_secretsmanager_secret.redis[0].arn,
      aws_secretsmanager_secret.sqs.arn,
    ]

    principals {
      type        = "AWS"
      identifiers = var.allowed_iam_principals
    }
  }
}

resource "aws_secretsmanager_secret_policy" "main" {
  secret_id = aws_secretsmanager_secret.database.id

  policy = data.aws_iam_policy_document.secret_read.json
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "database_secret_arn" {
  description = "ARN do secret de banco de dados"
  value       = aws_secretsmanager_secret.database.arn
}

output "redis_secret_arn" {
  description = "ARN do secret do Redis"
  value       = try(aws_secretsmanager_secret.redis[0].arn, null)
}

output "sqs_secret_arn" {
  description = "ARN do secret do SQS"
  value       = aws_secretsmanager_secret.sqs.arn
}

# ──────────────────────────────────────────────────────────────────────────────
# Variáveis do módulo secrets
# ──────────────────────────────────────────────────────────────────────────────

variable "environment" {
  description = "Nome do ambiente"
  type        = string
}

variable "prefix" {
  description = "Prefixo para nomear recursos"
  type        = string
  default     = "spot-render"
}

variable "kms_key_id" {
  description = "KMS Key ID para encriptação (opcional)"
  type        = string
  default     = null
}

variable "db_username" {
  description = "Usuário do banco de dados"
  type        = string
  default     = "render_admin"
}

variable "db_password" {
  description = "Senha do banco de dados"
  type        = string
  sensitive   = true
  default     = "changeme123!"
}

variable "db_host" {
  description = "Host do banco de dados"
  type        = string
  default     = "localhost"
}

variable "db_name" {
  description = "Nome do banco de dados"
  type        = string
  default     = "renderqueue"
}

variable "redis_host" {
  description = "Host do Redis"
  type        = string
  default     = "localhost"
}

variable "redis_password" {
  description = "Senha do Redis (opcional)"
  type        = string
  sensitive   = true
  default     = null
}

variable "sqs_queue_url" {
  description = "URL da fila SQS principal"
  type        = string
  default     = ""
}

variable "sqs_dlq_url" {
  description = "URL da fila DLQ SQS"
  type        = string
  default     = ""
}

variable "allowed_iam_principals" {
  description = "Lista de ARNs IAM que podem ler os secrets"
  type        = list(string)
  default     = []
}

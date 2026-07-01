# ──────────────────────────────────────────────────────────────────────────────
# Variáveis do módulo monitoring
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

variable "aws_region" {
  description = "Região AWS"
  type        = string
  default     = "us-east-1"
}

variable "alert_email" {
  description = "Email para receber alertas (opcional)"
  type        = string
  default     = null
}

variable "serverless_max_capacity" {
  description = "Capacidade máxima do Aurora Serverless v2 em ACUs"
  type        = number
  default     = 16
}

variable "sqs_queue_depth_threshold" {
  description = "Limite de profundidade da fila SQS para alarmar"
  type        = number
  default     = 100
}

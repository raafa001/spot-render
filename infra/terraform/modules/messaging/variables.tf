# ──────────────────────────────────────────────────────────────────────────────
# Variáveis do módulo messaging
# ──────────────────────────────────────────────────────────────────────────────

variable "environment" {
  description = "Nome do ambiente (prd, staging, dev)"
  type        = string
}

variable "prefix" {
  description = "Prefixo para nomear recursos (ex: spot-render)"
  type        = string
  default     = "spot-render"
}

variable "allowed_vpce_ids" {
  description = "Lista de VPC Endpoint IDs para permitir acesso à fila (opcional)"
  type        = list(string)
  default     = []
}

variable "queue_depth_alarm_threshold" {
  description = "Limite de mensagens na fila para disparar alarme"
  type        = number
  default     = 100
}

variable "alert_topic_arns" {
  description = "Lista de ARNs de SNS Topics para envio de alertas"
  type        = list(string)
  default     = []
}

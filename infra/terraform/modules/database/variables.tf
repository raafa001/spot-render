# ──────────────────────────────────────────────────────────────────────────────
# Variáveis do módulo database (Aurora PostgreSQL Serverless v2)
# ──────────────────────────────────────────────────────────────────────────────

variable "environment" {
  description = "Nome do ambiente (prd, staging, dev)"
  type        = string
}

variable "prefix" {
  description = "Prefixo para nomear recursos"
  type        = string
  default     = "spot-render"
}

variable "vpc_id" {
  description = "ID da VPC"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR da VPC para regra de entrada"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_ids" {
  description = "Lista de IDs das subnets (pelo menos 2 para multi-AZ)"
  type        = list(string)
}

variable "db_name" {
  description = "Nome do banco de dados"
  type        = string
  default     = "renderqueue"
}

variable "username" {
  description = "Usuário administrador"
  type        = string
  default     = "render_admin"
}

variable "password" {
  description = "Senha do banco (use Secrets Manager em produção)"
  type        = string
  sensitive   = true
  default     = "changeme123!"
}

variable "engine_version" {
  description = "Versão do Aurora PostgreSQL"
  type        = string
  default     = "15.6"
}

variable "kms_key_id" {
  description = "KMS Key ID para encriptação (opcional, usa AWS managed se vazio)"
  type        = string
  default     = null
}

# ─── Serverless v2 Configuration ───────────────────────────────────────────────

variable "serverless_min_capacity" {
  description = "Capacidade mínima do Aurora Serverless v2 em ACUs (0.5 - 96)"
  type        = number
  default     = 0.5
}

variable "serverless_max_capacity" {
  description = "Capacidade máxima do Aurora Serverless v2 em ACUs (0.5 - 96)"
  type        = number
  default     = 16
}

# ─── Replication & HA ─────────────────────────────────────────────────────────

variable "enable_read_replicas" {
  description = "Habilita read replicas para escalar leitura"
  type        = bool
  default     = true
}

variable "num_read_replicas" {
  description = "Número de read replicas (0-5)"
  type        = number
  default     = 1
}

variable "enable_global_db" {
  description = "Habilita Aurora Global Database para DR entre regiões"
  type        = bool
  default     = false
}

# ─── Backup & Recovery ────────────────────────────────────────────────────────

variable "backup_retention_days" {
  description = "Dias de retenção de backups automatizados (1-35)"
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Protege contra exclusão acidental (habilitar em produção)"
  type        = bool
  default     = true
}

# ─── Monitoring ────────────────────────────────────────────────────────────────

variable "enable_monitoring" {
  description = "Habilita Performance Insights e Enhanced Monitoring"
  type        = bool
  default     = true
}

variable "alert_topic_arns" {
  description = "Lista de ARNs de SNS Topics para alertas"
  type        = list(string)
  default     = []
}

# ──────────────────────────────────────────────────────────────────────────────
# Variáveis do módulo cache (ElastiCache Redis)
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

variable "node_type" {
  description = "Tipo de instância do ElastiCache (cache.r6g.small = ~$25/mês, cache.r6g.medium = ~$50/mês)"
  type        = string
  default     = "cache.r6g.small"
}

variable "num_cache_clusters" {
  description = "Número de nós de cache (2 = 1 primary + 1 replica, multi-AZ)"
  type        = number
  default     = 2
}

variable "engine_version" {
  description = "Versão do Redis"
  type        = string
  default     = "7.1"
}

variable "auth_enabled" {
  description = "Habilita AUTH token para conexão"
  type        = bool
  default     = true
}

variable "snapshot_retention_days" {
  description = "Dias de retenção de snapshots"
  type        = number
  default     = 7
}

variable "alert_topic_arns" {
  description = "Lista de ARNs de SNS Topics para alertas"
  type        = list(string)
  default     = []
}

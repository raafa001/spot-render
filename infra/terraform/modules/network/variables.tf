variable "create" {
  description = "Controla a criação dos recursos de rede."
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "CIDR principal da VPC."
  type        = string
}

variable "private_subnets" {
  description = "CIDRs das subnets privadas."
  type        = list(string)
}

variable "public_subnets" {
  description = "CIDRs das subnets públicas."
  type        = list(string)
}

variable "environment" {
  description = "Nome do ambiente para tagging."
  type        = string
}

variable "enable_flow_logs" {
  description = "Ativa AWS Flow Logs para a VPC."
  type        = bool
  default     = true
}

variable "flow_logs_retention_days" {
  description = "Retenção dos logs em dias (mínimo 365 para compliance)."
  type        = number
  default     = 400
}

variable "flow_logs_kms_key_arn" {
  description = "ARN de uma KMS Key existente para criptografar o CloudWatch Log Group. Se vazio, o módulo cria uma."
  type        = string
  default     = null
}

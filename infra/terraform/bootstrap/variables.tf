variable "bucket_name" {
  description = "Nome do bucket S3 dedicado ao state do Terraform"
  type        = string
  default     = "spot-render-terraform-state"
}

variable "aws_region" {
  description = "Região AWS alvo"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Profile AWS opcional para execuções locais"
  type        = string
  default     = null
}

variable "object_lock_default_retention_days" {
  description = "Retenção padrão (dias) aplicada aos objetos do state via Object Lock"
  type        = number
  default     = 30
}

variable "object_lock_mode" {
  description = "Modo de retenção do Object Lock (COMPLIANCE ou GOVERNANCE)"
  type        = string
  default     = "COMPLIANCE"
}

variable "allow_delete_without_mfa_principals" {
  description = "Lista de ARNs (roles/usuários) autorizados a deletar objetos sem MFA (ex.: pipelines)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags adicionais aplicadas ao bucket e KMS"
  type        = map(string)
  default     = {}
}

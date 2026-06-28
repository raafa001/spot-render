variable "create_rds" {
  description = "Cria (ou não) o banco via RDS."
  type        = bool
  default     = true
}

variable "create_local_statefulset" {
  description = "Cria o PostgreSQL local em Kubernetes."
  type        = bool
  default     = false
}

variable "engine_version" {
  description = "Versão do PostgreSQL."
  type        = string
}

variable "instance_class" {
  description = "Classe da instância RDS."
  type        = string
}

variable "allocated_storage" {
  description = "Storage do RDS (GiB)."
  type        = number
}

variable "db_name" {
  description = "Nome do banco."
  type        = string
}

variable "username" {
  description = "Usuário admin."
  type        = string
}

variable "password" {
  description = "Senha admin."
  type        = string
  sensitive   = true
}

variable "subnet_ids" {
  description = "Subnets privadas do RDS."
  type        = list(string)
  default     = []
}

variable "vpc_security_group_ids" {
  description = "Security Groups permitidos."
  type        = list(string)
  default     = []
}

variable "vpc_id" {
  description = "ID da VPC onde o RDS será provisionado (necessário quando nenhum SG é informado)."
  type        = string
  default     = null
}

variable "vpc_cidr" {
  description = "CIDR da VPC para liberar acesso interno."
  type        = string
  default     = null
}

variable "local_namespace" {
  description = "Namespace local."
  type        = string
}

variable "local_storage_size" {
  description = "Tamanho do PVC local."
  type        = string
}

variable "storage_class_name" {
  description = "StorageClass usado no PVC local."
  type        = string
}

variable "enable_monitoring" {
  description = "Ativa Performance Insights/Monitoramento."
  type        = bool
  default     = true
}

variable "ca_cert_identifier" {
  description = "Certificado TLS utilizado pelo RDS para criptografia in-transit."
  type        = string
  default     = "rds-ca-rsa4096-g1"
}

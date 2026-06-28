variable "create" {
  description = "Controla a criação do cluster."
  type        = bool
  default     = true
}

variable "cluster_name" {
  description = "Nome do cluster EKS."
  type        = string
}

variable "cluster_version" {
  description = "Versão do Kubernetes desejada."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets privadas usadas pelo cluster."
  type        = list(string)
  default     = []
}

variable "vpc_id" {
  description = "VPC alvo do cluster."
  type        = string
  default     = null
}

variable "desired_size" {
  description = "Tamanho desejado do node group padrão."
  type        = number
}

variable "min_size" {
  description = "Tamanho mínimo do node group padrão."
  type        = number
}

variable "max_size" {
  description = "Tamanho máximo do node group padrão."
  type        = number
}

variable "gpu_instance_types" {
  description = "Lista de instâncias com GPU suportadas."
  type        = list(string)
}

variable "enable_karpenter" {
  description = "Provisiona recursos auxiliares para Karpenter."
  type        = bool
  default     = true
}

variable "karpenter_namespace" {
  description = "Namespace alvo para o Karpenter."
  type        = string
  default     = "karpenter"
}

variable "kubernetes_version" {
  description = "Versão do Kubernetes usada para addons."
  type        = string
}

variable "aws_auth_admin_arns" {
  description = "Lista de ARNs com permissão admin no aws-auth."
  type        = list(string)
  default     = []
}

variable "map_roles" {
  description = "Entradas extra para mapRoles."
  type = list(object({
    rolearn  = string
    username = string
    groups   = list(string)
  }))
  default = []
}

variable "map_users" {
  description = "Entradas extra para mapUsers."
  type = list(object({
    userarn  = string
    username = string
    groups   = list(string)
  }))
  default = []
}

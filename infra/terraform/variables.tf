variable "environment" {
  description = "Nome lógico do ambiente (local, staging, prd)."
  type        = string
  default     = "local"
}

variable "enable_aws" {
  description = "Habilita o provisionamento dos recursos AWS (false para laboratório local)."
  type        = bool
  default     = false
}

variable "aws_region" {
  description = "Região AWS alvo."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Profile AWS CLI a ser usado nas credenciais compartilhadas."
  type        = string
  default     = "default"
}

variable "aws_shared_config_files" {
  description = "Lista de arquivos de configuração compartilhados da AWS CLI."
  type        = list(string)
  default     = ["~/.aws/config"]
}

variable "aws_shared_credentials_files" {
  description = "Lista de arquivos de credenciais compartilhados da AWS CLI."
  type        = list(string)
  default     = ["~/.aws/credentials"]
}

variable "default_tags" {
  description = "Tags adicionais aplicadas a todos os recursos."
  type        = map(string)
  default     = {}
}

variable "vpc_cidr" {
  description = "CIDR principal da VPC na AWS."
  type        = string
  default     = "10.20.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "Lista de CIDRs para subnets privadas."
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]
}

variable "public_subnet_cidrs" {
  description = "Lista de CIDRs para subnets públicas."
  type        = list(string)
  default     = ["10.20.101.0/24", "10.20.102.0/24"]
}

variable "enable_flow_logs" {
  description = "Controla a criação de Flow Logs para inspeção de tráfego."
  type        = bool
  default     = true
}

variable "eks_cluster_name" {
  description = "Nome do cluster EKS."
  type        = string
  default     = "spot-render-eks"
}

variable "eks_cluster_version" {
  description = "Versão do Kubernetes no EKS."
  type        = string
  default     = "1.29"
}

variable "eks_node_group_desired" {
  description = "Tamanho desejado do node group padrão."
  type        = number
  default     = 2
}

variable "eks_node_group_min" {
  description = "Mínimo do node group padrão."
  type        = number
  default     = 1
}

variable "eks_node_group_max" {
  description = "Máximo do node group padrão."
  type        = number
  default     = 6
}

variable "eks_gpu_instance_types" {
  description = "Tipos de instância com GPU aceitos pelo node group."
  type        = list(string)
  default     = ["g5.xlarge", "g5.2xlarge"]
}

variable "enable_karpenter" {
  description = "Habilita recursos de suporte ao Karpenter (IAM, namespace)."
  type        = bool
  default     = true
}

variable "karpenter_namespace" {
  description = "Namespace onde o Karpenter será instalado."
  type        = string
  default     = "karpenter"
}

variable "aws_auth_admin_arns" {
  description = "Lista de ARNs (IAM) com acesso administrativo ao cluster via aws-auth."
  type        = list(string)
  default     = []
}

variable "eks_map_roles" {
  description = "Mapa extra de roles para o aws-auth ConfigMap."
  type = list(object({
    rolearn  = string
    username = string
    groups   = list(string)
  }))
  default = []
}

variable "eks_map_users" {
  description = "Mapa extra de usuários para o aws-auth ConfigMap."
  type = list(object({
    userarn  = string
    username = string
    groups   = list(string)
  }))
  default = []
}

variable "database_engine_version" {
  description = "Versão do PostgreSQL (RDS ou StatefulSet)."
  type        = string
  default     = "15"
}

variable "database_instance_class" {
  description = "Classe da instância RDS."
  type        = string
  default     = "db.m6g.large"
}

variable "database_allocated_storage" {
  description = "Armazenamento alocado para o RDS (GiB)."
  type        = number
  default     = 200
}

variable "database_name" {
  description = "Nome lógico do banco de dados."
  type        = string
  default     = "renderqueue"
}

variable "database_username" {
  description = "Usuário administrador do banco."
  type        = string
  default     = "render_admin"
}

variable "database_password" {
  description = "Senha do banco (utilize SSM/Secrets em produção)."
  type        = string
  sensitive   = true
  default     = "changeme123!"
}

variable "database_enable_monitoring" {
  description = "Habilita logs/performance insights."
  type        = bool
  default     = true
}

variable "local_namespace" {
  description = "Namespace onde recursos locais (StatefulSet PostgreSQL) serão aplicados."
  type        = string
  default     = "infra-local"
}

variable "local_postgres_storage_size" {
  description = "Tamanho do PVC local para o PostgreSQL."
  type        = string
  default     = "20Gi"
}

variable "local_storage_class_name" {
  description = "StorageClass local (ex: local-path)."
  type        = string
  default     = "local-path"
}

variable "kubeconfig_path" {
  description = "Caminho para o kubeconfig utilizado nas conexões locais."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_host" {
  description = "Endpoint manual do cluster (opcional)."
  type        = string
  default     = null
}

variable "kube_token" {
  description = "Token de acesso ao cluster (quando não se usa kubeconfig)."
  type        = string
  default     = null
}

variable "kube_client_certificate" {
  description = "Certificado do cliente Kubernetes (base64)."
  type        = string
  default     = null
}

variable "kube_client_key" {
  description = "Chave do cliente Kubernetes (base64)."
  type        = string
  default     = null
}

variable "kube_cluster_ca_certificate" {
  description = "CA do cluster Kubernetes (base64)."
  type        = string
  default     = null
}

variable "tf_state_bucket" {
  description = "Nome do bucket S3 para o backend remoto do Terraform."
  type        = string
  default     = "spot-render-terraform-state"
}

variable "tf_state_lock_table" {
  description = "Nome da tabela DynamoDB usada como lock do state."
  type        = string
  default     = "spot-render-terraform-lock"
}

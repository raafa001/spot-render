# ──────────────────────────────────────────────────────────────────────────────
# Variáveis do Terraform Root
# Spot Render Platform - Infraestrutura completa
# ──────────────────────────────────────────────────────────────────────────────

# ─── Ambiente ────────────────────────────────────────────────────────────────

variable "environment" {
  description = "Nome lógico do ambiente (local, staging, prd)"
  type        = string
  default     = "local"
}

variable "prefix" {
  description = "Prefixo global para nomear recursos"
  type        = string
  default     = "spot-render"
}

variable "enable_aws" {
  description = "Habilita o provisionamento dos recursos AWS (false para laboratório local)"
  type        = bool
  default     = false
}

variable "aws_region" {
  description = "Região AWS alvo"
  type        = string
  default     = "us-east-1"
}

# ─── Rede ─────────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR principal da VPC na AWS"
  type        = string
  default     = "10.20.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "Lista de CIDRs para subnets privadas"
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]
}

variable "public_subnet_cidrs" {
  description = "Lista de CIDRs para subnets públicas"
  type        = list(string)
  default     = ["10.20.101.0/24", "10.20.102.0/24"]
}

variable "enable_flow_logs" {
  description = "Controla a criação de Flow Logs para inspeção de tráfego"
  type        = bool
  default     = true
}

# ─── EKS ───────────────────────────────────────────────────────────────────────

variable "eks_cluster_name" {
  description = "Nome do cluster EKS"
  type        = string
  default     = "spot-render-eks"
}

variable "eks_cluster_version" {
  description = "Versão do Kubernetes no EKS"
  type        = string
  default     = "1.35"
}

variable "eks_node_group_desired" {
  description = "Tamanho desejado do node group padrão"
  type        = number
  default     = 2
}

variable "eks_node_group_min" {
  description = "Mínimo do node group padrão"
  type        = number
  default     = 1
}

variable "eks_node_group_max" {
  description = "Máximo do node group padrão"
  type        = number
  default     = 6
}

variable "eks_gpu_instance_types" {
  description = "Tipos de instância com GPU aceitos pelo node group"
  type        = list(string)
  default     = ["g5.xlarge", "g5.2xlarge"]
}

variable "enable_karpenter" {
  description = "Habilita recursos de suporte ao Karpenter (IAM, namespace)"
  type        = bool
  default     = true
}

variable "karpenter_namespace" {
  description = "Namespace onde o Karpenter será instalado"
  type        = string
  default     = "karpenter"
}

variable "eks_map_roles" {
  description = "Mapa extra de roles para o aws-auth ConfigMap"
  type = list(object({
    rolearn  = string
    username = string
    groups   = list(string)
  }))
  default = []
}

variable "eks_map_users" {
  description = "Mapa extra de usuários para o aws-auth ConfigMap"
  type = list(object({
    userarn  = string
    username = string
    groups   = list(string)
  }))
  default = []
}

variable "aws_auth_admin_arns" {
  description = "Lista de ARNs (IAM) com acesso administrativo ao cluster via aws-auth"
  type        = list(string)
  default     = []
}

# ─── Aurora PostgreSQL ─────────────────────────────────────────────────────────

variable "database_engine_version" {
  description = "Versão do Aurora PostgreSQL"
  type        = string
  default     = "15.6"
}

variable "database_name" {
  description = "Nome lógico do banco de dados"
  type        = string
  default     = "renderqueue"
}

variable "database_username" {
  description = "Usuário administrador do banco"
  type        = string
  default     = "render_admin"
}

variable "database_password" {
  description = "Senha do banco (utilize SSM/Secrets em produção)"
  type        = string
  sensitive   = true
  default     = "changeme123!"
}

# ─── Aurora Serverless v2 ─────────────────────────────────────────────────────

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

# ─── Aurora Replication ───────────────────────────────────────────────────────

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

variable "alert_email" {
  description = "Email para receber alertas do CloudWatch (opcional)"
  type        = string
  default     = null
}

# ─── Amazon SQS ───────────────────────────────────────────────────────────────

variable "queue_depth_alarm_threshold" {
  description = "Limite de mensagens na fila para disparar alarme"
  type        = number
  default     = 100
}

# ─── ElastiCache Redis ────────────────────────────────────────────────────────

variable "redis_node_type" {
  description = "Tipo de instância do ElastiCache (cache.r6g.small = ~$25/mês)"
  type        = string
  default     = "cache.r6g.small"
}

variable "redis_num_cache_clusters" {
  description = "Número de nós de cache (2 = 1 primary + 1 replica para multi-AZ)"
  type        = number
  default     = 2
}

variable "redis_engine_version" {
  description = "Versão do Redis"
  type        = string
  default     = "7.1"
}

variable "enable_redis_auth" {
  description = "Habilita AUTH token para conexão Redis"
  type        = bool
  default     = true
}

variable "redis_password" {
  description = "Senha do Redis"
  type        = string
  sensitive   = true
  default     = null
}

variable "redis_snapshot_retention_days" {
  description = "Dias de retenção de snapshots Redis"
  type        = number
  default     = 7
}

# ─── Secrets Manager ──────────────────────────────────────────────────────────

variable "kms_key_id" {
  description = "KMS Key ID para encriptação (opcional, usa AWS managed se vazio)"
  type        = string
  default     = null
}

variable "allowed_iam_principals" {
  description = "Lista de ARNs IAM que podem ler os secrets"
  type        = list(string)
  default     = []
}

# ─── Local Infrastructure (Kind/Minikube) ────────────────────────────────────

variable "local_namespace" {
  description = "Namespace onde recursos locais (PostgreSQL StatefulSet) serão aplicados"
  type        = string
  default     = "infra-local"
}

variable "local_postgres_storage_size" {
  description = "Tamanho do PVC local para o PostgreSQL"
  type        = string
  default     = "20Gi"
}

variable "local_storage_class_name" {
  description = "StorageClass local (ex: local-path)"
  type        = string
  default     = "local-path"
}

variable "kubeconfig_path" {
  description = "Caminho para o kubeconfig utilizado nas conexões locais"
  type        = string
  default     = "~/.kube/config"
}

# ─── Terraform Backend ────────────────────────────────────────────────────────

variable "tf_state_bucket" {
  description = "Nome do bucket S3 para o backend remoto do Terraform"
  type        = string
  default     = "spot-render-terraform-state"
}

# ─── AWS Credentials (para Terraform Cloud/AGENT) ─────────────────────────────

variable "aws_profile" {
  description = "Profile AWS CLI a ser usado nas credenciais compartilhadas"
  type        = string
  default     = "default"
}

variable "aws_shared_config_files" {
  description = "Lista de arquivos de configuração compartilhados da AWS CLI"
  type        = list(string)
  default     = ["~/.aws/config"]
}

variable "aws_shared_credentials_files" {
  description = "Lista de arquivos de credenciais compartilhados da AWS CLI"
  type        = list(string)
  default     = ["~/.aws/credentials"]
}

# ─── Tags ─────────────────────────────────────────────────────────────────────

variable "default_tags" {
  description = "Tags adicionais aplicadas a todos os recursos"
  type        = map(string)
  default     = {}
}

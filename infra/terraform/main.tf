# ──────────────────────────────────────────────────────────────────────────────
# Spot Render - Terraform Root
# Provisão completa de infraestrutura para AWS EKS + Aurora + SQS + Redis
# ──────────────────────────────────────────────────────────────────────────────

locals {
  is_local = var.environment == "local"
}

# ─── Rede ─────────────────────────────────────────────────────────────────────

module "network" {
  source = "./modules/network"

  create           = var.enable_aws
  vpc_cidr         = var.vpc_cidr
  private_subnets  = var.private_subnet_cidrs
  public_subnets   = var.public_subnet_cidrs
  environment      = var.environment
  enable_flow_logs = var.enable_flow_logs
}

# ─── EKS Cluster ───────────────────────────────────────────────────────────────

module "eks" {
  source = "./modules/eks"

  create              = var.enable_aws
  cluster_name        = var.eks_cluster_name
  cluster_version     = var.eks_cluster_version
  subnet_ids          = module.network.private_subnet_ids
  vpc_id              = module.network.vpc_id
  desired_size        = var.eks_node_group_desired
  min_size            = var.eks_node_group_min
  max_size            = var.eks_node_group_max
  gpu_instance_types  = var.eks_gpu_instance_types
  enable_karpenter    = var.enable_karpenter
  karpenter_namespace = var.karpenter_namespace
  kubernetes_version  = var.eks_cluster_version
  aws_auth_admin_arns = var.aws_auth_admin_arns
  map_roles           = var.eks_map_roles
  map_users           = var.eks_map_users
}

# ─── Aurora PostgreSQL (Serverless v2) ─────────────────────────────────────────

module "database" {
  source = "./modules/database"

  environment = var.environment

  # Configuração do Aurora Serverless v2
  engine_version         = var.database_engine_version
  db_name               = var.database_name
  username              = var.database_username
  password              = var.database_password

  # Rede
  vpc_id                 = module.network.vpc_id
  vpc_cidr               = var.vpc_cidr
  subnet_ids             = module.network.private_subnet_ids

  # Serverless v2
  serverless_min_capacity = var.serverless_min_capacity
  serverless_max_capacity = var.serverless_max_capacity

  # HA e Replicação
  enable_read_replicas   = var.enable_read_replicas
  num_read_replicas      = var.num_read_replicas
  enable_global_db       = var.enable_global_db

  # Backup
  backup_retention_days  = var.backup_retention_days
  deletion_protection     = var.enable_aws ? true : false # Sempre true em produção

  # Monitoring
  enable_monitoring       = var.enable_monitoring
  alert_topic_arns       = var.alert_topic_arns
}

# ─── Amazon SQS (Job Queue + DLQ) ─────────────────────────────────────────────

module "messaging" {
  source = "./modules/messaging"

  environment                  = var.environment
  prefix                       = var.prefix
  queue_depth_alarm_threshold   = var.queue_depth_alarm_threshold
  alert_topic_arns             = var.alert_topic_arns
}

# ─── ElastiCache Redis ─────────────────────────────────────────────────────────

module "cache" {
  source = "./modules/cache"

  environment = var.environment
  prefix     = var.prefix

  vpc_id     = module.network.vpc_id
  vpc_cidr   = var.vpc_cidr
  subnet_ids = module.network.private_subnet_ids

  node_type              = var.redis_node_type
  num_cache_clusters     = var.redis_num_cache_clusters
  engine_version         = var.redis_engine_version
  auth_enabled           = var.enable_redis_auth
  snapshot_retention_days = var.redis_snapshot_retention_days

  alert_topic_arns = var.alert_topic_arns
}

# ─── Secrets Manager ──────────────────────────────────────────────────────────

module "secrets" {
  source = "./modules/secrets"

  environment = var.environment
  prefix     = var.prefix

  kms_key_id = var.kms_key_id

  db_username = var.database_username
  db_password = var.database_password
  db_host     = module.database.cluster_endpoint
  db_name     = var.database_name

  redis_host     = module.cache.redis_endpoint
  redis_password = var.enable_redis_auth ? var.redis_password : null

  sqs_queue_url = module.messaging.jobs_queue_url
  sqs_dlq_url   = module.messaging.dlq_url

  allowed_iam_principals = var.allowed_iam_principals
}

# ─── Monitoring (CloudWatch + Alertas) ────────────────────────────────────────

module "monitoring" {
  source = "./modules/monitoring"

  environment = var.environment
  prefix     = var.prefix
  aws_region = var.aws_region

  serverless_max_capacity = var.serverless_max_capacity
  sqs_queue_depth_threshold = var.queue_depth_alarm_threshold

  alert_email = var.alert_email
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "network_summary" {
  description = "Resumo da rede provisionada"
  value = {
    vpc_id          = module.network.vpc_id
    private_subnets = module.network.private_subnet_ids
    public_subnets  = module.network.public_subnet_ids
    nat_gateways    = module.network.nat_gateway_ids
  }
}

output "eks_summary" {
  description = "Dados principais do cluster EKS"
  value = {
    cluster_name    = module.eks.cluster_name
    endpoint        = module.eks.cluster_endpoint
    oidc_arn        = module.eks.oidc_provider_arn
    nodegroup_arn   = module.eks.node_group_arn
  }
}

output "database_summary" {
  description = "Informações do banco Aurora PostgreSQL"
  value = {
    cluster_endpoint        = module.database.cluster_endpoint
    cluster_reader_endpoint = module.database.cluster_reader_endpoint
    cluster_arn             = module.database.cluster_arn
    cluster_id              = module.database.cluster_id
    security_group_id       = module.database.security_group_id
    global_cluster_arn      = module.database.global_cluster_arn
  }
}

output "messaging_summary" {
  description = "Informações do SQS"
  value = {
    jobs_queue_url = module.messaging.jobs_queue_url
    jobs_queue_arn = module.messaging.jobs_queue_arn
    dlq_url        = module.messaging.dlq_url
    dlq_arn        = module.messaging.dlq_arn
  }
}

output "cache_summary" {
  description = "Informações do ElastiCache Redis"
  value = {
    redis_endpoint = module.cache.redis_endpoint
    redis_port     = module.cache.redis_port
    redis_arn      = module.cache.redis_arn
  }
}

output "secrets_summary" {
  description = "ARNs dos secrets no Secrets Manager"
  value = {
    database_secret_arn = module.secrets.database_secret_arn
    redis_secret_arn   = module.secrets.redis_secret_arn
    sqs_secret_arn     = module.secrets.sqs_secret_arn
  }
}

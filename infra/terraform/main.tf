locals {
  is_local = var.environment == "local"
}

# Módulo de rede - cria VPC/Subnets na AWS ou apenas expõe dados locais.
module "network" {
  source = "./modules/network"

  create           = var.enable_aws
  vpc_cidr         = var.vpc_cidr
  private_subnets  = var.private_subnet_cidrs
  public_subnets   = var.public_subnet_cidrs
  environment      = var.environment
  enable_flow_logs = var.enable_flow_logs
}

# Módulo EKS - somente quando enable_aws = true.
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

# Banco de dados - StatefulSet local OU RDS Multi-AZ.
module "database" {
  source = "./modules/database"

  create_rds               = var.enable_aws
  create_local_statefulset = local.is_local

  engine_version         = var.database_engine_version
  instance_class         = var.database_instance_class
  allocated_storage      = var.database_allocated_storage
  db_name                = var.database_name
  username               = var.database_username
  password               = var.database_password
  subnet_ids             = module.network.database_subnet_ids
  vpc_security_group_ids = []
  vpc_id                 = module.network.vpc_id
  vpc_cidr               = var.vpc_cidr

  local_namespace    = var.local_namespace
  local_storage_size = var.local_postgres_storage_size
  storage_class_name = var.local_storage_class_name
  enable_monitoring  = var.database_enable_monitoring
}

output "network_summary" {
  description = "Resumo da rede provisionada (ou parâmetros locais)."
  value = {
    vpc_id          = module.network.vpc_id
    private_subnets = module.network.private_subnet_ids
    public_subnets  = module.network.public_subnet_ids
    nat_gateways    = module.network.nat_gateway_ids
  }
}

output "eks_summary" {
  description = "Dados principais do cluster EKS (nulo em modo local)."
  value = {
    cluster_name  = module.eks.cluster_name
    endpoint      = module.eks.cluster_endpoint
    oidc_arn      = module.eks.oidc_provider_arn
    nodegroup_arn = module.eks.node_group_arn
  }
}

output "database_summary" {
  description = "Informações do banco de dados (RDS ou StatefulSet)."
  value = {
    rds_endpoint = module.database.rds_endpoint
    secret_arn   = module.database.secret_arn
    service_name = module.database.local_service_name
    pvc_name     = module.database.local_pvc_name
  }
}

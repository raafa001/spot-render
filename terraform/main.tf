terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0" # Usando a versão mais recente da AWS Provider (maior que 5.0)
    }
  }
  required_version = ">= 1.1"
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.36.0" # **Versão mais recente do módulo EKS**
  count   = var.deploy_kubernetes ? 1 : 0

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version
  vpc_id          = module.network[0].vpc_id
  subnet_ids      = module.network[0].subnet_ids
  tags            = var.tags
  eks_managed_node_groups = var.eks_node_groups
}

module "network" {
  source = "./network"
  count  = var.deploy_network ? 1 : 0
}

module "permissions" {
  source = "./permissions"
  count  = var.deploy_permissions ? 1 : 0
}

module "s3" {
  source = "./s3"
  count  = var.deploy_s3 ? 1 : 0
}

# Definição das variáveis (mantendo as existentes)
variable "deploy_kubernetes" {
  type    = bool
  default = true
}

variable "deploy_network" {
  type    = bool
  default = true
}

variable "deploy_permissions" {
  type    = bool
  default = true
}

variable "deploy_s3" {
  type    = bool
  default = true
}

variable "cluster_name" {
  type    = string
  default = "spot-render"
}

variable "cluster_version" {
  type    = string
  default = "1.27"
}

variable "tags" {
  type = map(string)
  default = {
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
  }
}

variable "eks_node_groups" {
  type = map(object({
    desired_capacity = number
    max_capacity     = number
    min_capacity     = number
    instance_type    = string
    k8s_version      = string
    capacity_type    = string
    update_policy    = string
    tags             = map(string)
  }))
  default = {
    spot-nodes = {
      desired_capacity = 2
      max_capacity     = 3
      min_capacity     = 1
      instance_type    = "g4dn.xlarge" # Exemplo de instância com GPU
      k8s_version      = "1.27"
      capacity_type    = "SPOT"
      update_policy     = "Auto"
      tags = {
        Environment = "dev"
        Project     = "renderizacao"
        AutoOff     = "true"
      }
    }
  }
}

# Outputs (ajustando para a nova versão do módulo EKS)
output "vpc_id" {
  value = module.network[0].vpc_id
}

output "subnet_ids" {
  value = module.network[0].subnet_ids
}

output "eks_cluster_id" {
  value = module.eks[0].eks_cluster_id # **Acessando o output correto na versão mais recente**
}

output "s3_source_bucket_arn" {
  value = module.s3[0].s3_bucket_arn
}

output "s3_output_bucket_arn" {
  value = module.s3[0].s3_bucket_arn
}
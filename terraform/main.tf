terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = var.tags
  }
}

# =============================================================================
# Modules
# =============================================================================

module "network" {
  source = "./network"
  count  = var.deploy_network ? 1 : 0

  vpc_cidr            = var.vpc_cidr
  subnet_cidr         = var.subnet_cidr
  environment         = var.environment
  project_name        = var.project_name
}

module "permissions" {
  source = "./permissions"
  count  = var.deploy_permissions ? 1 : 0

  environment  = var.environment
  project_name = var.project_name
}

module "s3" {
  source = "./s3"
  count  = var.deploy_s3 ? 1 : 0

  environment  = var.environment
  project_name = var.project_name
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.36"
  count   = var.deploy_kubernetes ? 1 : 0

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version
  vpc_id          = module.network[0].vpc_id
  subnet_ids      = module.network[0].subnet_ids

  eks_managed_node_groups = var.eks_node_groups

  tags = var.tags
}

# =============================================================================
# Variables
# =============================================================================

variable "deploy_network" {
  description = "Whether to deploy the VPC/network module"
  type        = bool
  default     = true

  validation {
    condition     = can(tobool(var.deploy_network))
    error_message = "deploy_network must be a boolean value."
  }
}

variable "deploy_kubernetes" {
  description = "Whether to deploy the EKS cluster module"
  type        = bool
  default     = true

  validation {
    condition     = can(tobool(var.deploy_kubernetes))
    error_message = "deploy_kubernetes must be a boolean value."
  }
}

variable "deploy_permissions" {
  description = "Whether to deploy the IAM permissions module"
  type        = bool
  default     = true

  validation {
    condition     = can(tobool(var.deploy_permissions))
    error_message = "deploy_permissions must be a boolean value."
  }
}

variable "deploy_s3" {
  description = "Whether to deploy the S3 buckets module"
  type        = bool
  default     = true

  validation {
    condition     = can(tobool(var.deploy_s3))
    error_message = "deploy_s3 must be a boolean value."
  }
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "spot-render"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "subnet_cidr" {
  description = "CIDR block for the subnet"
  type        = string
  default     = "10.0.1.0/24"

  validation {
    condition     = can(cidrhost(var.subnet_cidr, 0))
    error_message = "subnet_cidr must be a valid IPv4 CIDR block."
  }
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "spot-render"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9\\-]*$", var.cluster_name))
    error_message = "cluster_name must start with a letter and contain only alphanumeric characters and hyphens."
  }
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.32"

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+$", var.cluster_version))
    error_message = "cluster_version must be in the format <major>.<minor> (e.g., 1.32)."
  }
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default = {
    Environment = "dev"
    Project     = "spot-render"
    ManagedBy   = "terraform"
    AutoOff     = "true"
  }
}

variable "eks_node_groups" {
  description = "Configuration for EKS managed node groups"
  type = map(object({
    desired_capacity = number
    max_capacity     = number
    min_capacity     = number
    instance_types   = list(string)
    capacity_type    = string
    disk_size        = optional(number, 20)
    labels           = optional(map(string), {})
    tags             = optional(map(string), {})
  }))
  default = {
    spot-nodes = {
      desired_capacity = 2
      max_capacity     = 3
      min_capacity     = 1
      instance_types   = ["g5dn.large"]
      capacity_type    = "SPOT"
      disk_size        = 20
      labels = {
        Environment = "dev"
        Project     = "spot-render"
      }
      tags = {
        Environment = "dev"
        Project     = "spot-render"
        AutoOff     = "true"
      }
    }
  }

  validation {
    condition = alltrue([
      for k, v in var.eks_node_groups :
      v.min_capacity <= v.desired_capacity && v.desired_capacity <= v.max_capacity
    ])
    error_message = "Each node group must satisfy: min_capacity <= desired_capacity <= max_capacity."
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "vpc_id" {
  description = "ID of the created VPC"
  value       = try(module.network[0].vpc_id, null)
}

output "subnet_ids" {
  description = "List of subnet IDs"
  value       = try(module.network[0].subnet_ids, null)
}

output "eks_cluster_id" {
  description = "ID of the EKS cluster"
  value       = try(module.eks[0].cluster_id, null)
}

output "eks_cluster_endpoint" {
  description = "Endpoint of the EKS cluster"
  value       = try(module.eks[0].cluster_endpoint, null)
}

output "eks_cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = try(module.eks[0].cluster_security_group_id, null)
}

output "s3_source_bucket_arn" {
  description = "ARN of the source S3 bucket"
  value       = try(module.s3[0].source_bucket_arn, null)
}

output "s3_output_bucket_arn" {
  description = "ARN of the output S3 bucket"
  value       = try(module.s3[0].output_bucket_arn, null)
}

output "iam_role_arn" {
  description = "ARN of the IAM role for EKS"
  value       = try(module.permissions[0].eks_role_arn, null)
}

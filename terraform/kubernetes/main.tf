# =============================================================================
# Kubernetes Module - EKS Cluster
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.36"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version
  vpc_id          = var.vpc_id
  subnet_ids      = var.subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    for k, v in var.eks_node_groups : k => {
      desired_size = v.desired_capacity
      max_size     = v.max_capacity
      min_size     = v.min_capacity

      instance_types = v.instance_types
      capacity_type  = v.capacity_type
      disk_size      = try(v.disk_size, 20)

      labels = merge(v.labels, {
        Environment = var.environment
        Project     = var.project_name
      })

      tags = merge(v.tags, {
        Environment = var.environment
        Project     = var.project_name
      })
    }
  }

  tags = var.tags
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9\\-]*$", var.cluster_name))
    error_message = "cluster_name must start with a letter and contain only alphanumeric characters and hyphens."
  }
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+$", var.cluster_version))
    error_message = "cluster_version must be in format <major>.<minor> (e.g., 1.32)."
  }
}

variable "vpc_id" {
  description = "ID of the VPC where the cluster will be deployed"
  type        = string
}

variable "subnets" {
  description = "List of subnet IDs for the EKS cluster"
  type        = list(string)

  validation {
    condition     = length(var.subnets) > 0
    error_message = "At least one subnet must be provided."
  }
}

variable "tags" {
  description = "Tags applied to the EKS cluster resources"
  type        = map(string)
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
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
    k8s_version      = optional(string)
    labels           = optional(map(string), {})
    tags             = optional(map(string), {})
  }))

  validation {
    condition = alltrue([
      for k, v in var.eks_node_groups :
      v.min_capacity <= v.desired_capacity && v.desired_capacity <= v.max_capacity
    ])
    error_message = "Each node group must satisfy: min_capacity <= desired_capacity <= max_capacity."
  }
}

output "cluster_id" {
  description = "ID of the EKS cluster"
  value       = module.eks.cluster_id
}

output "cluster_endpoint" {
  description = "Endpoint of the EKS cluster"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = module.eks.cluster_arn
}

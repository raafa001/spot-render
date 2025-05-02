variable "cluster_name" {
  type = string
}

variable "cluster_version" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnets" {
  type = list(string)
  description = "A lista de Subnet IDs para o cluster EKS."
}

variable "tags" {
  type = map(string)
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
      instance_type    = "g5dn.large" # Exemplo de instância com GPU
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
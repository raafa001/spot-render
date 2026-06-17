terraform {
  required_version = ">= 1.6.6"
  backend "s3" {
    # Para execução local, comente este bloco e crie um arquivo backend.override.tf com `backend "local" { path = "./terraform.tfstate" }`.
    bucket         = "spot-render-terraform-state"
    key            = "global/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "spot-render-terraform-lock"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.60"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.32"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.13"
    }
    tls = {
      source  = "hashicorp/tls"
      version = ">= 4.0"
    }
  }
}

# Provedor AWS: usado apenas quando enable_aws = true.
provider "aws" {
  region                   = var.aws_region
  profile                  = var.aws_profile
  shared_config_files      = var.aws_shared_config_files
  shared_credentials_files = var.aws_shared_credentials_files

  default_tags {
    tags = merge(
      {
        "Environment" = var.environment
        "Project"     = "spot-render"
      },
      var.default_tags
    )
  }
}

# Provedor Kubernetes: usado para recursos locais (StatefulSet do PostgreSQL)
# e para validações pontuais dentro dos módulos.
provider "kubernetes" {
  config_path            = var.kubeconfig_path
  host                   = var.kube_host
  token                  = var.kube_token
  client_certificate     = var.kube_client_certificate
  client_key             = var.kube_client_key
  cluster_ca_certificate = var.kube_cluster_ca_certificate
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

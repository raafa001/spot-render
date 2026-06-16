# Arquitetura do Projeto / Project Architecture

## PT-BR

### Visão Geral
O **spot-render** é uma infraestrutura como código (IaC) para orquestrar ambientes de renderização em nuvem usando AWS EKS com instâncias Spot para redução de custos.

### Estrutura de Diretórios

```
spot-render/
├── docs/                          # Documentação
├── kubernetes/                    # Manifests Kubernetes (Prometheus, Grafana, Network Policies)
├── scripts/                       # Shell scripts utilitários
├── terraform/                     # Infraestrutura como código Terraform
│   ├── kubernetes/                # Módulo EKS
│   ├── network/                   # Módulo VPC e Subnets
│   ├── permissions/               # Módulo IAM Roles e Policies
│   └── s3/                        # Módulo S3 Buckets
├── *.groovy                       # Pipelines Jenkins
└── pom.xml                        # Build Maven (código legado Java)
```

### Componentes Principais

1. **Jenkins Pipelines (Groovy)**: Automatizam CI/CD - code coverage, execução terraform, deploy kubernetes, start/stop de instâncias
2. **Terraform**: Provisiona infraestrutura AWS modular (VPC, EKS, S3, IAM)
3. **Kubernetes**: Manifests para monitoramento (Prometheus + Grafana) em cluster EKS
4. **Shell Scripts**: Utilitários para instalação de ferramentas, configuração Jenkins e gerenciamento de instâncias EC2

### Fluxo de Deploy

1. Pipeline Jenkins executa `terraform plan/apply` para provisionar rede, EKS, buckets S3 e permissões
2. Pipeline separado faz deploy dos manifests Kubernetes (Prometheus/Grafana) no cluster EKS
3. Scripts auxiliares gerenciam instâncias EC2 spot com tags AutoOff

---

## EN

### Overview
**spot-render** is an Infrastructure as Code (IaC) project to orchestrate cloud rendering environments using AWS EKS with Spot Instances for cost reduction.

### Directory Structure

```
spot-render/
├── docs/                          # Documentation
├── kubernetes/                    # Kubernetes manifests (Prometheus, Grafana, Network Policies)
├── scripts/                       # Utility shell scripts
├── terraform/                     # Terraform IaC
│   ├── kubernetes/                # EKS module
│   ├── network/                   # VPC and Subnets module
│   ├── permissions/               # IAM Roles and Policies module
│   └── s3/                        # S3 Buckets module
├── *.groovy                       # Jenkins pipelines
└── pom.xml                        # Maven build (legacy Java code)
```

### Main Components

1. **Jenkins Pipelines (Groovy)**: Automate CI/CD - code coverage, terraform execution, kubernetes deploy, instance start/stop
2. **Terraform**: Provisions modular AWS infrastructure (VPC, EKS, S3, IAM)
3. **Kubernetes**: Monitoring manifests (Prometheus + Grafana) for EKS cluster
4. **Shell Scripts**: Utilities for tool installation, Jenkins configuration, and EC2 instance management

### Deploy Flow

1. Jenkins pipeline runs `terraform plan/apply` to provision network, EKS, S3 buckets, and IAM permissions
2. Separate pipeline deploys Kubernetes manifests (Prometheus/Grafana) to EKS cluster
3. Helper scripts manage spot EC2 instances tagged with AutoOff

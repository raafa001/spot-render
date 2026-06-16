# 🎬 spot-render

Infraestrutura como código para ambientes de renderização em nuvem com EKS Spot.

Infrastructure as Code for cloud rendering environments with EKS Spot.

---

## PT-BR

### Visão Geral

**spot-render** é um projeto de Infraestrutura como Código (IaC) que automatiza o provisionamento e gerenciamento de ambientes de renderização em nuvem utilizando **AWS EKS** com **instâncias Spot** para redução de custos.

### Estrutura do Projeto

```
spot-render/
├── docs/                          # Documentação do projeto
│   └── ARCHITECTURE.md            # Arquitetura detalhada
├── kubernetes/                    # Manifests Kubernetes
│   ├── grafana-deployment.yaml    # Deployment do Grafana
│   ├── grafana-service.yaml       # Service do Grafana
│   ├── prometheus-deployment.yaml # Deployment do Prometheus
│   ├── prometheus-service.yaml    # Service do Prometheus
│   ├── prometheus-configmap.yaml  # Config do Prometheus
│   ├── prometheus-rules.yaml      # Regras de alerta
│   ├── namespaces.yaml            # Namespaces Kubernetes
│   └── network-policy.yaml        # Políticas de rede
├── scripts/                       # Scripts utilitários
│   ├── configure-jenkins.sh       # Configuração de plugins Jenkins
│   ├── install-tools.sh           # Instalação de ferramentas
│   ├── start-instances.sh         # Inicia instâncias EC2 spot
│   └── stop-instances.sh          # Para instâncias EC2 spot
├── terraform/                     # Terraform IaC
│   ├── main.tf                    # Configuração principal
│   ├── kubernetes/                # Módulo EKS
│   ├── network/                   # Módulo VPC/Subnets
│   ├── permissions/               # Módulo IAM
│   └── s3/                        # Módulo S3
├── *.groovy                       # Pipelines Jenkins CI/CD
├── pom.xml                        # Build Maven (legado)
└── README.md                      # Este arquivo
```

### Pré-requisitos

- **Terraform** >= 1.5
- **AWS CLI** configurado com credenciais
- **kubectl** para gerenciar o cluster EKS
- **Jenkins** (opcional) para execução das pipelines
- **Docker** (opcional) para execução de scans de segurança

### Como Usar

```bash
# Clone o repositório
git clone https://github.com/raafa001/spot-render.git
cd spot-render

# Inicialize e aplique o Terraform
cd terraform
terraform init
terraform plan
terraform apply

# Deploy dos manifests Kubernetes
kubectl apply -f kubernetes/namespaces.yaml
kubectl apply -f kubernetes/ -n monitoring
```

### Pipelines Jenkins

| Pipeline | Descrição |
|----------|-----------|
| `code-coverage.groovy` | Scans de segurança (Checkov, Trivy, Hadolint, ShellCheck) |
| `execute-terraform.groovy` | Execução de Terraform (plan/apply/destroy) |
| `terraform-pipeline.groovy` | Pipeline simplificada para Terraform |
| `kubernetes-deploy.groovy` | Deploy de manifests Kubernetes |
| `jenkins-start-instances.groovy` | Inicia instâncias EC2 spot |
| `jenkins-stop-instances.groovy` | Para instâncias EC2 spot |

### Segurança

- Buckets S3 com criptografia AES-256 habilitada
- Bloqueio de acesso público S3
- IAM roles com privilégios mínimos
- Instâncias Spot com tags AutoOff para economia
- Security groups restritos por porta e protocolo
- Network Policies Kubernetes para isolamento

---

## EN

### Overview

**spot-render** is an Infrastructure as Code (IaC) project that automates the provisioning and management of cloud rendering environments using **AWS EKS** with **Spot Instances** for cost optimization.

### Project Structure

```
spot-render/
├── docs/                          # Project documentation
│   └── ARCHITECTURE.md            # Detailed architecture
├── kubernetes/                    # Kubernetes manifests
│   ├── grafana-deployment.yaml    # Grafana deployment
│   ├── grafana-service.yaml       # Grafana service
│   ├── prometheus-deployment.yaml # Prometheus deployment
│   ├── prometheus-service.yaml    # Prometheus service
│   ├── prometheus-configmap.yaml  # Prometheus config
│   ├── prometheus-rules.yaml      # Alert rules
│   ├── namespaces.yaml            # Kubernetes namespaces
│   └── network-policy.yaml        # Network policies
├── scripts/                       # Utility scripts
│   ├── configure-jenkins.sh       # Jenkins plugin setup
│   ├── install-tools.sh           # Tool installation
│   ├── start-instances.sh         # Start EC2 spot instances
│   └── stop-instances.sh          # Stop EC2 spot instances
├── terraform/                     # Terraform IaC
│   ├── main.tf                    # Root configuration
│   ├── kubernetes/                # EKS module
│   ├── network/                   # VPC/Subnets module
│   ├── permissions/               # IAM module
│   └── s3/                        # S3 module
├── *.groovy                       # Jenkins CI/CD pipelines
├── pom.xml                        # Maven build (legacy)
└── README.md                      # This file
```

### Prerequisites

- **Terraform** >= 1.5
- **AWS CLI** configured with credentials
- **kubectl** to manage EKS cluster
- **Jenkins** (optional) for pipeline execution
- **Docker** (optional) for security scans

### Quick Start

```bash
# Clone the repository
git clone https://github.com/raafa001/spot-render.git
cd spot-render

# Initialize and apply Terraform
cd terraform
terraform init
terraform plan
terraform apply

# Deploy Kubernetes manifests
kubectl apply -f kubernetes/namespaces.yaml
kubectl apply -f kubernetes/ -n monitoring
```

### Jenkins Pipelines

| Pipeline | Description |
|----------|-------------|
| `code-coverage.groovy` | Security scans (Checkov, Trivy, Hadolint, ShellCheck) |
| `execute-terraform.groovy` | Terraform execution (plan/apply/destroy) |
| `terraform-pipeline.groovy` | Simplified Terraform pipeline |
| `kubernetes-deploy.groovy` | Kubernetes manifest deployment |
| `jenkins-start-instances.groovy` | Start EC2 spot instances |
| `jenkins-stop-instances.groovy` | Stop EC2 spot instances |

### Security

- S3 buckets with AES-256 encryption enabled
- S3 public access blocked
- IAM roles with least privilege
- Spot instances with AutoOff tags for cost savings
- Restricted security groups by port and protocol
- Kubernetes Network Policies for isolation

---

## Licença / License

MIT

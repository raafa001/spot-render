# 🎬 Spot Render Platform

> **PT-BR:** Plataforma de infraestrutura e CI/CD para renderização distribuída usando Blender/Cycles em Kubernetes (local ou AWS EKS) com GitOps e pipelines GitHub Actions.
>
> **EN:** Infrastructure + CI/CD platform for distributed Blender/Cycles rendering on Kubernetes (local or AWS EKS) with GitOps and GitHub Actions pipelines.

---

## PT-BR

### Visão Geral

- **IaC unificada**: Terraform modular (rede, EKS, banco) com comutador `enable_aws` para alternar entre laboratório local (Kind/Minikube) e AWS EKS + RDS + EFS.
- **GitOps pronto**: Kustomize (base + `overlays/local` e `overlays/prd`) consumidos pelo ArgoCD (`argocd/application.yaml`).
- **Render pipeline**: API FastAPI + workers Blender GPU com Argo Rollouts (canário 10→90% em 5 min), HPAs, ingress com WAF/ModSecurity e métricas Prometheus (ServiceMonitor/PodMonitor + dashboard Grafana).
- **Developer Experience**: Documentação bilíngue, scripts simples para ingestão de arquivos `.blend`, GitHub Actions com linting/testes/build/push/Trivy + trigger GitOps.

### Estrutura do Repositório

```
spot-render/
├── .github/workflows/ci.yml         # Pipeline principal (lint → sonar → test → build → scans → GitOps trigger)
├── .github/workflows/terraform-plan.yml   # `terraform plan` automático (push + cron)
├── .github/workflows/terraform-apply.yml  # `terraform apply` manual com aprovação
├── argocd/application.yaml          # Aplicação ArgoCD (overlay prd)
├── docs/
│   ├── ARCHITECTURE.md              # Referência arquitetural
│   └── OPERATIONS.md                # Guia passo-a-passo (local/AWS, ingestão, troubleshooting)
├── infra/terraform/                # Terraform (providers/main/variables/outputs + módulos network/eks/database)
├── k8s/                            # Kustomize base + overlays local/prd
├── observability/grafana-dashboard-rendering.json
├── services/api/                   # API FastAPI + requirements
├── workers/blender-runner/         # Entrypoint e Dockerfile do worker Blender
├── Dockerfile.api / Dockerfile.worker
└── requirements-dev.txt            # Dependências de testes (pytest etc.)
```

Artefatos legados (Groovy pipelines, scripts Jenkins, `terraform/` antigo) permanecem na branch `main` para consulta histórica; o fluxo atual vive em `feat/platform-foundation`.

### Pré-requisitos

- Terraform ≥ **1.6.6**
- Python 3.11+ + `pip`
- Docker (Buildx e QEMU habilitados)
- kubectl 1.29+, kustomize 5+, Helm 3.14+
- AWS CLI configurado (quando `enable_aws=true`)
- Cluster local (Kind, Minikube ou Docker Desktop) com StorageClass `local-path`
- Secrets obrigatórios no repositório (GitHub → Settings → Secrets): `SONAR_HOST_URL`, `SONAR_TOKEN`, `AWS_DEPLOY_ROLE_ARN`, `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `ARGOCD_WEBHOOK_URL`. Caso `SONAR_*` não estejam definidos o job exibirá apenas um aviso e seguirá.
> ℹ️ **Dica:** se estiver rodando o SonarQube localmente (ex.: WSL2), use o endereço completo acessível a partir do runner self-hosted (por exemplo `http://127.0.0.1:9000` ou o IP da interface), antes de salvar `SONAR_HOST_URL` nos secrets.

### Quickstart Local (Kind/Minikube)

```bash
# 1. Build das imagens
docker build -f Dockerfile.api -t local/spot-render-api:dev .
docker build -f Dockerfile.worker -t local/spot-render-worker:dev .

# 2. Aplicar overlay local
kubectl apply -k k8s/overlays/local

# 3. Alimentar a fila
export ASSETS_DIR="$HOME/spot-render-assets"
mkdir -p "$ASSETS_DIR"/{queue,output,completed,failed}
cp sample.blend "$ASSETS_DIR"/queue/
```

Workers monitoram `/mnt/assets/queue` (montado via PV local-path). Arquivos prontos vão para `output/<job>` e originais são movidos para `completed/`/`failed/` conforme status.

### Quickstart AWS (EKS + RDS + EFS)

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Atualize bucket/tabela/variáveis e defina enable_aws = true
terraform init -backend-config="bucket=<state-bucket>" -backend-config="dynamodb_table=<lock-table>"
terraform apply -var "environment=prd" -var "enable_aws=true"

# GitOps
kubectl apply -f argocd/application.yaml
argocd app sync spot-render-prd
```

O overlay `prd` troca StorageClass para EFS CSI, ingress para ALB + WAF e imagens hospedadas no ECR. Karpenter/Cluster Autoscaler cuidarão dos nós GPU `g5.*` (ver módulo `infra/terraform/modules/eks`).

### Workflows GitHub Actions

| Workflow | Quando roda | O que faz |
| --- | --- | --- |
| `ci.yml` | push/PR em `main` | ShellCheck + Hadolint, SonarQube (`SONAR_HOST_URL`/`SONAR_TOKEN`), Trivy FS, pytest com cobertura, build/push condicional (Docker Hub vs. ECR), Trivy nas imagens e trigger ArgoCD |
| `terraform-plan.yml` | push em `infra/terraform/**`, cron 00h/08h/16h e manual | `terraform fmt -check` + `terraform plan` com upload do artefato `tfplan`, ajudando a detectar drift de forma contínua |
| `terraform-apply.yml` | manual (`workflow_dispatch`) | Executa `terraform apply` após aprovação humana (configure o ambiente protegido **platform-infra** no GitHub repo settings) |

### Alimentando a Fila de Renderização

1. **Upload local**: copie `.blend` para `$ASSETS_DIR/queue`. O worker processa automaticamente.
2. **Bucket S3**: envie para `s3://spot-render-assets/queue/` e registre o job via API (implementação sugerida em `docs/OPERATIONS.md`).
3. **Portal Web**: template Backstage recomendado para artistas enviarem arquivos e monitorarem o status.

### Observabilidade e Saúde

- `k8s/base/podmonitor-worker.yaml` e `servicemonitor-api.yaml` permitem scraping por Prometheus Operator existente.
- `observability/grafana-dashboard-rendering.json` fornece visualização de frames/min, CPU workers, 5xx e latência p95.
- Health-checks: `/healthz` (API) + probes/`/tmp/worker.ready` (workers). HPAs usam métricas de CPU/threads.

### Documentação Complementar

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): detalhes de módulos Terraform, estratégia GitOps e segurança.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md): guia completo (pré-reqs, troubleshooting, ingestão, verificação).

---

## EN

### Overview

- **Unified IaC**: Modular Terraform (network, EKS, database) with `enable_aws` switch to hop between local labs (Kind/Minikube) and AWS (EKS + RDS + EFS).
- **GitOps-first**: Kustomize base + overlays consumed by ArgoCD (`argocd/application.yaml`).
- **Render pipeline**: FastAPI control plane + Blender GPU workers on Argo Rollouts (10→90% canary, 5‑min steps), HPAs, hardened ingress (WAF/ModSecurity) and Prometheus/Grafana assets.
- **DX focused**: bilingual docs, folder-based queue workflow, GitHub Actions covering lint/test/build/scan and triggering ArgoCD webhooks.

### Repository Structure

Same as above (see tree). Legacy Jenkins/Groovy assets remain on `main`; the modern platform is developed on feature branches like `feat/platform-foundation` and will replace `main` after review.

### Prerequisites

- Terraform ≥ **1.6.6**
- Python 3.11+, Docker w/ Buildx, kubectl 1.29+, kustomize 5+, Helm 3.14+
- AWS CLI (when targeting AWS)
- Local cluster with RWX-capable StorageClass (`local-path`)
- Repository secrets: `SONAR_HOST_URL`, `SONAR_TOKEN`, `AWS_DEPLOY_ROLE_ARN`, `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `ARGOCD_WEBHOOK_URL`. If `SONAR_*` are missing, the Sonar job will issue a warning and continue.

### Local Quickstart

1. Build API/worker images (`Dockerfile.api`, `Dockerfile.worker`).
2. `kubectl apply -k k8s/overlays/local`.
3. Drop `.blend` files into `$ASSETS_DIR/queue`; outputs land under `$ASSETS_DIR/output/<job>`.

### AWS Quickstart

1. Configure `infra/terraform/terraform.tfvars` (buckets, roles, `enable_aws=true`).
2. `terraform init && terraform apply -var environment=prd`.
3. Apply `argocd/application.yaml` and let ArgoCD sync `k8s/overlays/prd` (EFS CSI, ALB ingress, ECR images).

### GitHub Actions Workflows

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `ci.yml` | push/PR on `main` | ShellCheck + Hadolint, SonarQube (`SONAR_HOST_URL` / `SONAR_TOKEN` secrets), Trivy filesystem, pytest, Buildx push (Docker Hub vs. ECR), Trivy on both images, ArgoCD webhook |
| `terraform-plan.yml` | push to `infra/terraform/**`, cron 00:00/08:00/16:00 UTC, manual | Runs `terraform fmt -check` + `terraform plan` and uploads the plan artifact for drift detection |
| `terraform-apply.yml` | manual (`workflow_dispatch`) | Executes `terraform apply` after human approval (protect the `platform-infra` environment to enforce reviewers) |

### Feeding the Queue

| Method | Description |
| --- | --- |
| Local folder | Copy `.blend` into `$ASSETS_DIR/queue`; worker loop handles rendering |
| S3 bucket | Upload to `s3://spot-render-assets/queue/` and call the API to enqueue |
| Web portal | Optional Backstage template to collect uploads + track status |

### Documentation & Support

- Use `docs/OPERATIONS.md` for step-by-step operations, health/HPA validation, troubleshooting.
- Use `docs/ARCHITECTURE.md` for design rationale, module references, and security considerations.

### License

MIT
### Acesso via ArgoCD / Ingress

- **ArgoCD**: depois que o PR for mergeado em `main`, o webhook do job `gitops-trigger` atualiza automaticamente a Application `spot-render-prd`. No dashboard você deve ver `Synced / Healthy`. Caso esteja `OutOfSync`, rode `argocd app sync spot-render-prd`.
- **Local (NGINX Ingress)**: expõe `render-api` em `https://render.local` (porta 443). Adicione `render.local` ao `/etc/hosts` apontando para o IP do ingress controller e aceite o certificado provisionado pelo cert-manager.
- **AWS (ALB)**: o overlay `prd` aponta para `https://render.spot-render.example.com` (porta 443). Ajuste o ARN do certificado ACM, WAF ACL e DNS conforme sua conta.
- **Fallback**: `kubectl port-forward svc/render-api -n rendering 8080:8080` e acesse `http://localhost:8080/healthz`.

# Spot Render – Infraestrutura e CI/CD

## 1. Visão Geral / Overview

> **PT-BR:** A plataforma Spot Render fornece uma trilha completa de Dev→Prod para workloads de renderização Blender/Cycles, combinando IaC (Terraform), Kustomize + GitOps (ArgoCD) e observabilidade pronta para uso. O design prioriza GPU on-demand/spot, armazenamento compartilhado RWX (local-path ou EFS) e esteira segura (WAF, TLS automático, análises em canário via Argo Rollouts).
>
> **EN:** Spot Render delivers an end-to-end Dev→Prod path for Blender/Cycles workloads by mixing IaC (Terraform), Kustomize + GitOps (ArgoCD), and ready-to-use observability. The design favors on-demand/spot GPUs, shared RWX storage (local-path or EFS), and a secure release train (WAF, automated TLS, canary analysis via Argo Rollouts).

> **Stacks atualizados / Refreshed stacks:**
> - **API:** Python 3.12 + FastAPI 0.136.3 (uvicorn 0.49.0, Redis 8.0.1, pydantic-settings 2.14.2).
> - **Workers:** Blender 5.1.0 (tarball oficial) executando sobre CUDA 12.6 runtime para suportar GPUs g5/g6.

## 2. Terraform

> **PT-BR:**
> - Estrutura padrão (`providers.tf`, `main.tf`, `variables.tf`, `outputs.tf`) com backend remoto S3 versionado + Object Lock (sem DynamoDB) e documentação para usar `backend.override.tf` em modo local.
> - Módulo `network`: VPC / subnets públicas e privadas, NAT Gateway por AZ, Flow Logs com CloudWatch + IAM dedicado, SG específico do PostgreSQL.
> - Módulo `eks`: Cluster 1.29, node group GPU (`g5.xlarge`), addons control-plane, IRSA + OIDC, papéis do Karpenter/Karpenter instance profile, regras `aws-auth` via Access Entries.
> - Módulo `database`: RDS PostgreSQL Multi-AZ (monitoring/PI habilitados) ou StatefulSet local com PVC `local-path`, probes TCP/readiness, secreta gerada por Terraform.
>
> **EN:**
> - Standard layout (`providers.tf`, `main.tf`, `variables.tf`, `outputs.tf`) with an Object-Lock-enabled S3 backend (no DynamoDB) and guidance on switching to a local backend via `backend.override.tf`.
> - `network` module: VPC / public + private subnets, one NAT Gateway per AZ, Flow Logs with CloudWatch + dedicated IAM, PostgreSQL-specific SG.
> - `eks` module: Kubernetes 1.29 cluster, GPU node group (`g5.xlarge`), control plane addons, IRSA + OIDC, Karpenter controller/instance profiles, and `aws-auth` entries managed via Access Entries.
> - `database` module: Multi-AZ PostgreSQL RDS (monitoring/PI enabled) or a local StatefulSet using the `local-path` PVC, TCP/readiness probes, and secrets provisioned by Terraform.

## 3. Kubernetes & GitOps

> **PT-BR:**
> - Kustomize (`k8s/base`) concentra Namespace, ConfigMaps, PVC RWX, ServiceAccounts com IRSA, NetworkPolicy baseline e PriorityClass. Overlays `local` (StorageClass local-path + PV hostPath) e `prd` (EFS CSI, ingress ALB) apenas ajustam storage, imagens e annotations específicas.
> - API exposta via Rollout (Argo Rollouts) com canário 10%→90% em passos de 5 minutos. Ingress (`networking.k8s.io/v1`) adiciona rate limiting NGINX + ModSecurity CRS e integrações WAF/ALB + cert-manager.
> - Workers GPU: Deployment `blender-worker` com toleration `nvidia.com/gpu`, nodeAffinity custom (`spot-render.io/gpu-capable`), file-based queue (`/mnt/assets/queue`). O entrypoint roda em loop, move jobs `queue → output/completed`, publica métricas HTTP e atualiza arquivos de saúde (`/tmp/worker.ready`).
> - HPAs (`autoscaling/v2`) acompanham CPU/threads de API (min 3, max 15) e workers (min 2, max 30). Pod/ServiceMonitor expõem métricas para o Prometheus Operator já existente.
> - GitOps: `argocd/application.yaml` aponta para `k8s/overlays/prd` com `automated sync + prune`, `CreateNamespace` e `selfHeal` habilitados.
>
> **EN:**
> - Kustomize (`k8s/base`) contains Namespace, ConfigMaps, RWX PVC, ServiceAccounts w/ IRSA, baseline NetworkPolicy, and PriorityClass. `local` overlay (local-path StorageClass + hostPath PV) and `prd` overlay (EFS CSI, ALB ingress) merely tweak storage, images, and environment-specific annotations.
> - API shipped as an Argo Rollouts canary (10%→90% in 5-minute increments). The `networking.k8s.io/v1` Ingress adds NGINX rate limiting + ModSecurity CRS and integrates with WAF/ALB + cert-manager.
> - GPU workers: `blender-worker` Deployment with `nvidia.com/gpu` toleration, custom nodeAffinity (`spot-render.io/gpu-capable`), file-based queue (`/mnt/assets/queue`). The entrypoint loops, moves jobs `queue → output/completed`, exposes HTTP metrics, and refreshes `/tmp/worker.ready` for probes.
> - HPAs (`autoscaling/v2`) track API CPU/threads (min 3, max 15) and workers (min 2, max 30). Pod/ServiceMonitors let the existing Prometheus Operator scrape metrics instantly.
> - GitOps: `argocd/application.yaml` tracks `k8s/overlays/prd` with automated sync + prune, `CreateNamespace`, and `selfHeal` turned on.

## 4. Observabilidade / Observability

> **PT-BR:** PodMonitor (workers) + ServiceMonitor (API) direcionam métricas para o Prometheus Operator. O AnalysisTemplate `render-api-http-errors` usa consultas 5xx para bloquear rollouts quando a taxa >1%. Dashboard JSON (`observability/grafana-dashboard-rendering.json`) mostra frames/min, CPU workers, taxa 5xx e latência p95 da API.
>
> **EN:** The PodMonitor (workers) and ServiceMonitor (API) feed metrics into the existing Prometheus Operator. The `render-api-http-errors` AnalysisTemplate leverages 5xx queries to block rollouts when the error rate >1%. The JSON dashboard (`observability/grafana-dashboard-rendering.json`) displays frames/min, worker CPU, 5xx rate, and API p95 latency.

## 5. CI/CD

> **PT-BR:** A esteira foi particionada: `ci.yml` roda lint (ShellCheck + Hadolint), SonarQube, Trivy FS, pytest, build/push (Docker Hub vs. ECR) e os scans de imagem + trigger Argo; `terraform-plan.yml` executa `terraform plan` automaticamente (push + cron 3x/dia) para flagrar drift; `terraform-apply.yml` só roda via botão (`workflow_dispatch`) e exige aprovação humana usando o ambiente protegido `platform-infra`.
>
> **EN:** The delivery flow is split: `ci.yml` runs lint (ShellCheck + Hadolint), SonarQube, Trivy FS, pytest, build/push (Docker Hub vs. ECR) plus image scans and the Argo webhook; `terraform-plan.yml` runs `terraform plan` automatically (push + thrice-daily cron) to detect drift; `terraform-apply.yml` is manual (`workflow_dispatch`) and gated by the protected `platform-infra` environment for human approval.

## 6. Operação / Operations

> **PT-BR:**
> 1. Ajuste `terraform.tfvars` com buckets/roles reais e rode `terraform apply` para cada ambiente (`environment` variável).
> 2. Aplique `k8s/overlays/local` para laboratórios; deixe o ArgoCD sincronizar `prd` (EFS + ALB + WAF) automaticamente.
> 3. Configure os secrets (AWS Secrets Manager ou SOPS+Age) apontados no `ExternalSecret` `render-db`.
> 4. Alimente a fila colocando arquivos `.blend` em `/mnt/assets/queue` (local path ou EFS) ou via API/web intake. Workers movem o arquivo para `completed/` e escrevem frames em `/mnt/assets/output/*`.
> 5. Use o guia `docs/OPERATIONS.md` para validar health-checks, HPAs e intake.
>
> **EN:**
> 1. Adjust `terraform.tfvars` with real buckets/roles and run `terraform apply` per environment (`environment` variable).
> 2. Apply `k8s/overlays/local` for labs; let ArgoCD sync `prd` (EFS + ALB + WAF) automatically.
> 3. Wire secrets (AWS Secrets Manager or SOPS+Age) referenced by the `render-db` `ExternalSecret`.
> 4. Feed the queue by dropping `.blend` files into `/mnt/assets/queue` (local path or EFS) or via API/web intake. Workers move the source to `completed/` and write frames under `/mnt/assets/output/*`.
> 5. Follow `docs/OPERATIONS.md` to validate health checks, HPAs, and intake flows.

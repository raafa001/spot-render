---
title: Spot Render - Guia Operacional
tags: [terraform, kubernetes, argocd, gpu]
difficulty: advanced
time: 60 minutos
---

# Spot Render - Guia Operacional / Operational Guide

## Objetivo / Goal

> **PT-BR:** Ensinar como preparar o ambiente local, promover para AWS e alimentar a fila de renderização utilizando os manifests Kustomize, pipeline GitHub Actions e módulos Terraform deste repositório.
>
> **EN:** Explain how to spin up the local environment, promote to AWS, and feed the rendering queue using this repo's Kustomize manifests, GitHub Actions pipeline, and Terraform modules.

## Pré-requisitos / Prerequisites

- [ ] **PT-BR:** `kubectl`, `kustomize` e `helm` 3.14+ instalados localmente.  
      **EN:** `kubectl`, `kustomize`, and `helm` 3.14+ installed locally.
- [ ] **PT-BR:** Acesso a um cluster local (Kind/Minikube) com suporte a StorageClass `local-path`.  
      **EN:** Access to a local cluster (Kind/Minikube) with a `local-path` StorageClass available.
- [ ] **PT-BR:** Conta AWS com IAM Role que permita `eks:*`, `ec2:*`, `rds:*`, `iam:*` e `s3:*`.  
      **EN:** AWS account with an IAM role that grants `eks:*`, `ec2:*`, `rds:*`, `iam:*`, and `s3:*`.
- [ ] **PT-BR:** Docker Buildx habilitado para publicar imagens no Docker Hub ou Amazon ECR.  
      **EN:** Docker Buildx enabled to publish images to Docker Hub or Amazon ECR.
- [ ] **PT-BR:** Diretório com arquivos `.blend` para testes.  
      **EN:** Folder storing `.blend` sample files for testing.

## Passo a Passo / Step by Step

### Passo 1: Preparar o cluster local / Prepare the local cluster

> **PT-BR:** Crie o diretório de ativos locais, inicialize o Kind/Minikube e aplique o overlay `local` via Kustomize.
>
> **EN:** Create the local asset folders, bootstrap Kind/Minikube, and apply the `local` overlay via Kustomize.

```bash
export ASSETS_DIR="$HOME/spot-render-assets"
mkdir -p "$ASSETS_DIR"/{queue,output,completed,failed}

minikube start --kubernetes-version=v1.29.4 --cpus=6 --memory=16g

kubectl apply -k k8s/overlays/local
```

> 💡 **PT-BR:** Ao usar Docker Desktop, monte o diretório `$ASSETS_DIR` em `/data/render-assets` para que o PV `render-assets-local` enxergue os arquivos.  
> 💡 **EN:** When using Docker Desktop, bind-mount `$ASSETS_DIR` into `/data/render-assets` so the `render-assets-local` PV can see the files.

#### Semear a fila com demos oficiais / Seed the queue with official demos

> **PT-BR:** Utilize o script `scripts/seed-render-queue.sh` para baixar o arquivo "Raycast Lines" do Blender e movê-lo automaticamente para a fila local. O script cria as pastas `queue/output/completed/failed` caso ainda não existam.  
> **EN:** Use the `scripts/seed-render-queue.sh` helper to download Blender's "Raycast Lines" demo file and drop it straight into the local queue. The script also prepares the `queue/output/completed/failed` folders if needed.

```bash
export ASSETS_DIR="$HOME/spot-render-assets"
./scripts/seed-render-queue.sh --assets-dir "$ASSETS_DIR"
```

> **Referência / Reference:** Blender demo files catalog ([blender.org/download/demo-files](https://www.blender.org/download/demo-files/)).

### Passo 2: Build e carga das imagens locais / Build & load local images

> **PT-BR:** Gere as imagens da API e do worker e carregue-as no cluster para evitar push externo.
>
> **EN:** Build the API and worker images and load them into the cluster to avoid external pushes.

```bash
docker build -f Dockerfile.api -t local/spot-render-api:dev .
docker build -f Dockerfile.worker -t local/spot-render-worker:dev .

kind load docker-image local/spot-render-api:dev
kind load docker-image local/spot-render-worker:dev
```

### Passo 3: Provisionar AWS com Terraform / Provision AWS via Terraform

> **PT-BR:** Atualize `terraform.tfvars`, inicialize o backend remoto (S3+DynamoDB) e aplique os módulos.
>
> **EN:** Update `terraform.tfvars`, initialize the remote backend (S3 + DynamoDB), and apply the modules.

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init \
  -backend-config="bucket=spot-render-terraform-state" \
  -backend-config="dynamodb_table=spot-render-terraform-lock" \
  -backend-config="region=us-east-1"

terraform apply -var "environment=prd" -var "enable_aws=true"
```

> 💡 **PT-BR:** Execute `terraform plan` diariamente (GitHub Actions agendado) para detectar drift.  
> 💡 **EN:** Run `terraform plan` daily (scheduled GitHub Actions) to detect drift.

### Passo 4: Configurar ArgoCD e GitOps / Configure ArgoCD & GitOps

> **PT-BR:** Garanta que o ArgoCD observe `argocd/application.yaml` e sincronize o overlay `prd`.
>
> **EN:** Ensure ArgoCD watches `argocd/application.yaml` and syncs the `prd` overlay.

```bash
kubectl apply -f argocd/application.yaml
argocd app sync spot-render-prd
```

### Passo 5: Alimentar a fila de renderização / Feed the render queue

> **PT-BR:** Existem três caminhos suportados; todos convergem para o diretório montado `/mnt/assets/queue` dentro dos pods.
>
> **EN:** Three supported paths exist; all converge into the `/mnt/assets/queue` mount inside pods.

1. **PT-BR:** *Upload local*: copie arquivos `.blend` para `$ASSETS_DIR/queue`. O Deployment `blender-worker` detectará o novo arquivo, renderizará para `$ASSETS_DIR/output/<nome>` e moverá o original para `completed/`.  
   **EN:** *Local upload*: copy `.blend` files into `$ASSETS_DIR/queue`. The `blender-worker` Deployment picks them up, renders into `$ASSETS_DIR/output/<name>`, and moves the original into `completed/`.
2. **PT-BR:** *Bucket S3*: carregue os arquivos em `s3://spot-render-assets/queue/` e use o endpoint `POST /jobs` (implementar na API) informando o caminho S3. O controller adiciona um placeholder `.blend` via CSI Driver (EFS) para os workers.  
   **EN:** *S3 bucket*: upload files to `s3://spot-render-assets/queue/` and call the (to-be-implemented) `POST /jobs` endpoint with the S3 path. The controller writes a placeholder `.blend` via the CSI driver (EFS) for the workers.
3. **PT-BR:** *Portal Web*: publique um pequeno frontend (ex.: Next.js + presigned URLs) que envia arquivos para o bucket e chama a API; template sugerido no Backstage como “Render Intake”.  
   **EN:** *Web portal*: deploy a tiny frontend (e.g., Next.js + presigned URLs) that uploads to the bucket and calls the API; use a Backstage template named “Render Intake”.

### Passo 6: Testes, health-checks e HPA / Tests, health checks & HPA

> **PT-BR:** Valide os health-checks (`/healthz`, probes dos workers) e monitore o HPA.
>
> **EN:** Validate the health checks (`/healthz`, worker probes) and watch the HPA behaviour.

```bash
# API
kubectl port-forward svc/render-api -n rendering 8080:8080 &

# Workers
kubectl logs deploy/blender-worker -n rendering -f

# HPA status
kubectl get hpa -n rendering
```

> 💡 **PT-BR:** Gere carga com `hey` ou `k6` para observar o Argo Rollouts + HPA elevando réplicas.  
> 💡 **EN:** Use `hey` or `k6` to see Argo Rollouts + HPA scaling replicas.

## Verificação / Verification

- [ ] **PT-BR:** `kubectl get pods -n rendering` mostra pods `render-api` e `blender-worker` prontos.  
      **EN:** `kubectl get pods -n rendering` shows ready `render-api` and `blender-worker` pods.
- [ ] **PT-BR:** `kubectl get hpa -n rendering` indica métricas coletadas e faixa `min/max`.  
      **EN:** `kubectl get hpa -n rendering` reports fetched metrics and `min/max` bounds.
- [ ] **PT-BR:** Frames renderizados aparecem em `$ASSETS_DIR/output/<job>/`.  
      **EN:** Rendered frames appear under `$ASSETS_DIR/output/<job>/`.
- [ ] **PT-BR:** Dashboard Grafana “Spot Render - Pipeline” mostra métricas em tempo real.  
      **EN:** Grafana dashboard “Spot Render - Pipeline” shows live metrics.

## Troubleshooting

| Problema / Problem | Causa provável / Likely cause | Solução / Fix |
|---|---|---|
| Pods `blender-worker` ficam em `CrashLoopBackOff` | **PT-BR:** Diretório `queue` não montado ou permissões incorretas. <br> **EN:** `queue` directory not mounted or wrong permissions. | **PT-BR:** Monte `$ASSETS_DIR` em `/data/render-assets` e garanta `chmod 775`. <br> **EN:** Bind-mount `$ASSETS_DIR` to `/data/render-assets` and ensure `chmod 775`. |
| HPA não escala | **PT-BR:** Metrics server ausente ou Prometheus sem acesso. <br> **EN:** Metrics server missing or Prometheus unreachable. | **PT-BR:** `kubectl top pods -n rendering`; instale metrics-server. <br> **EN:** `kubectl top pods -n rendering`; install metrics-server. |
| Render trava em AWS | **PT-BR:** Karpenter/EKS sem nós GPU disponíveis. <br> **EN:** Karpenter/EKS lacks available GPU nodes. | **PT-BR:** Verifique `karpenter` e quotas de GPU na região. <br> **EN:** Check `karpenter` and GPU quotas in the region. |

## Próximos Passos / Next Steps

- **PT-BR:** Implementar o endpoint `POST /jobs` na API para aceitar uploads assinados e integrar com filas SQS/Kafka.  
  **EN:** Implement the `POST /jobs` endpoint in the API to accept signed uploads and integrate with SQS/Kafka queues.
- **PT-BR:** Automatizar o portal web de intake no Backstage para que artistas enviem jobs sem acessar o cluster.  
  **EN:** Automate the intake web portal in Backstage so artists can submit jobs without cluster access.
- **PT-BR:** Adicionar políticas de ciclo de vida no bucket S3/EFS para arquivar frames antigos no Glacier.  
  **EN:** Add lifecycle policies on S3/EFS to archive old frames to Glacier.

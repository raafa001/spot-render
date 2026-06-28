## Spot Render — Blueprint Arquitetural

> **Status:** Aprovado em 28/06/2026  
> **Escopo:** Reorganização completa em múltiplos repositórios, infraestrutura AWS, pipelines CI/CD, canary com Argo Rollouts e observabilidade full-stack.

---

### 1. Visão Geral da Arquitetura

- **AWS Account**
  - VPC multi-AZ (subnets públicas/privadas, NAT, rotas).
  - EKS com node groups dedicados: `api`, `portal`, `workers` (Blender).
  - Buckets S3: `spot-render-input`, `spot-render-output`, `spot-render-error` (versionamento + lifecycle).
  - Secrets Manager: tokens, credenciais, configs sensíveis.
  - IRSA: roles específicos para API, portal e Argo workers com acesso mínimo ao S3/Secrets.
  - ingress-nginx/ALB + AWS WAF (TLS, rate limit, regras OWASP) para API/portal.

- **Fluxo principal**
  1. Upload via API/portal/CLI → grava em `s3://spot-render-input/{projeto}/{variacao}/{timestamp}/...` com metadados (funcionário, origem).
  2. Sensor S3 dispara Workflow Argo: download → `convert_materials.py` (FBX → Principled BSDF) → `render_blender.py` (Blender headless) → upload em output/error → grava métricas Prometheus.
  3. Observabilidade coleta `render_success_total`, `render_error_total`, `render_per_artist_total`, `render_queue_total`, `render_duration_seconds`, `canary_error_rate`, etc. Grafana exibe dashboards por projeto/artista e status de canary.

- **Deploy**
  - API e Portal usam **Argo Rollouts** (10% → 50% → 100%) com análise automática (Prometheus). Rollback automático se erro >1% ou p95 > 500ms.
  - Workers Blender publicados em ECR; Argo Workflows puxam a imagem.

- **CI/CD padrão**
  - Build → lint/test/coverage (≥80%) → Sonar → Trivy → push ECR → deploy (kubectl/argo). Sem exceções.

---

### 2. Repositórios

| Repositório | Conteúdo | Stack | CI/CD |
|-------------|----------|-------|-------|
| `spot-render-infra-aws` | Terraform (VPC, EKS, buckets, Secrets, IRSA, ingress+WAF). Backend **S3 apenas**. | Terraform 1.9 | `fmt` → `validate` → `plan` (auto) / `apply` (manual). |
| `spot-render-api` | FastAPI + boto3 + Prometheus metrics + CLI de upload. | Python 3.12 | lint/test/coverage ≥80% → Sonar → build Docker → Trivy → push ECR → deploy. |
| `spot-render-portal` | Next.js (upload UI, listagem de jobs). | Node 20/Next | lint/test → Sonar (JS) → build Docker → Trivy → push ECR → deploy. |
| `spot-render-cli` | CLI Python (configura funcionário local, faz upload). | Python | lint/test → pacote PyPI interno. |
| `spot-render-argo` | Workflows + sensores S3 + scripts Blender + Dockerfile worker. | YAML/Blender | lint manifests → build worker → push ECR → argo sync. |
| `spot-render-observability` | Exporter Prometheus, dashboards Grafana, alertas. | Prometheus/Grafana | lint json/yaml → publicar chart. |
| `spot-render-config` | Documentação central, runbooks, diagramas. | Markdown | lint docs. |

Cada repositório terá README PT/EN com quickstart, pipelines, dependências e links cruzados.

---

### 3. Fluxos Detalhados

#### Upload / API / CLI

- Endpoint `POST /uploads` recebe arquivo + `funcionario`, `empreendimento`, `variacao`, `origem`.  
- Campo opcional `renderlist` (CSV/XLSX) permite enviar listas de renderização atualizadas. Os arquivos fornecidos internamente (ex.: `render-list*.csv/xlsx`) permanecem fora do Git e apenas trafegam via API/portal.
- CLI (Python) salva o funcionário em `~/.spotrender/config` na primeira execução e aceita `--renderlist` opcional.  
- API escreve em S3 `spot-render-input/{projeto}/{variacao}/{timestamp}/…` e atualiza métricas (`render_queue_total`).

#### Argo Workflows

1. Sensor S3 detecta novo objeto.
2. Workflow com steps:
   - `fetch_input` (S3 → pod)  
   - `convert_materials.py` (FBX → Principled)  
   - `render_blender.py` (Blender headless)  
   - `upload_result` / `upload_error`  
   - `record_metrics` (Prometheus).  
3. Scripts em Python logam metadados (projeto, artista) para Prometheus.

#### Observabilidade

- Exporter expõe:  
  `render_success_total{projeto, artista}`, `render_error_total{projeto, artista}`, `render_queue_total{projeto}`, `render_duration_seconds`, `render_canary_requests_total{version}`, `render_canary_error_rate`.  
- Dashboard Grafana: visão geral, por projeto, por artista, comparativo canary vs stable.  
- Alertas Prometheus: erro >1% ou p95 > 500ms → rollback automático no Argo Rollouts.

---

### 4. Estrutura Terraform (spot-render-infra-aws)

```
terraform/
├── backend.tf (S3)
├── main.tf (instância módulos)
├── modules/
│   ├── vpc/
│   ├── eks/
│   ├── s3-buckets/
│   ├── irsa/
│   ├── secrets/
│   └── ingress-waf/
└── environments/
    ├── dev/
    └── prod/
```

- Buckets com versionamento, lifecycle e tags; IRSA associada às ServiceAccounts (API, portal, Argo worker).  
- Ingress/WAF: recurso que cria ALB ingress + AWS WAF ACL (regras OWASP, rate limit).  
- Secrets Manager para tokens (Sonar, API keys, credenciais Blender).  
- Outputs exportam endpoints (API/portal), ARNs dos buckets e nomes das roles IRSA.

---

### 5. Argo Rollouts & Canary

- Substituir Deployments por Rollouts com steps `setWeight 10 → pause → setWeight 50 → pause → setWeight 100`.  
- Analysis template usando métricas Prometheus:  
  - `metric: canary_error_rate` – query `sum(rate(http_requests_total{status!~"2..",version="canary"}[1m])) / sum(rate(http_requests_total{version="canary"}[1m]))` (threshold 0.01).  
  - `metric: canary_latency_p95` – query `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{version="canary"}[1m])) by (le))` (threshold 0.5s).  
- Rollback automático se qualquer métrica violar o limite.  
- Alertas Prometheus espelham as mesmas condições para visibilidade humana.

---

### 6. CI/CD Padrão (exemplo para API)

```yaml
name: CI

  push:
  pull_request:

  lint-test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Install deps
        run: pip install -r requirements-dev.txt
      - name: Tests
        run: pytest --cov=app --cov-report=xml --cov-fail-under=80
      - name: SonarQube
        env:
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
        run: sonar-scanner -Dsonar.projectKey=spot-render-api

  docker:
    needs: lint-test
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Login ECR
        uses: aws-actions/amazon-ecr-login@v2
      - name: Build & Push
        uses: docker/build-push-action@v6
        with:
          push: true
          tags: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com/spot-render-api:${{ github.sha }}
      - name: Deploy rollout
        run: |
          kubectl apply -f k8s/rollout.yaml
          kubectl argo rollouts promote spot-render-api || true
```

Demais repositórios seguem o mesmo padrão adaptando linguagem/stack.

---

### 7. Próximas Etapas & Times

- **@dev-staff**
  - Implementar API/CLI (FastAPI) + portal (Next.js) + scripts Argo (convert/render) + exporter Prometheus.
- **@devops-staff**
  - Codificar Terraform (infra-aws), manifests K8s (Argo Rollouts, ingress/WAF) e pipelines GitHub Actions.
- **@qa-staff**
  - Estratégia de testes: unit (API), integração (S3), E2E portal, validação Workflow Argo, cobertura ≥80%.
- **@dbre-staff**
  - Naming/tagging S3, lifecycle policy, custos, backup/retention e guidelines para Secrets Manager.
- **@sre-staff**
  - Dashboards Grafana, alertas Prometheus, runbooks (deploy/rollback, incidentes canary), SLO/SLI.

Cada repositório terá README PT/EN com quickstart, pipelines, referência a este blueprint e documentação adicional em `spot-render-config`.

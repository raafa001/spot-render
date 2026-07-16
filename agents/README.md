# AIOps Agents - spot-render

> **PT-BR:** Agentes autônomos de AIOps para operations de TI usando LLMs gratuitos (Ollama local).
> **EN:** Autonomous AIOps agents for IT operations using free LLMs (local Ollama).

---

## 🤖 Agentes Disponíveis

| Agente | Prioridade | Descrição |
|--------|-----------|-----------|
| **SecurityScanner** | 🔴 Alta | Scan CVEs, secrets, IaC misconfigs |
| **Documenter** | 🟡 Média | Auto-gera README, API docs, runbooks |
| **MonitorAgent** | 🔴 Alta | Métricas em tempo real, anomaly detection |
| **RootCauseAnalyzer** | 🔴 Alta | RCA automatizado com metodologia 5 Whys |
| **AlertGenerator** | 🟢 Baixa | Gera regras Prometheus/Grafana |
| **CapacityPlanner** | 🟢 Baixa | Forecasting, right-sizing |
| **IncidentResponder** | 🟡 Média | Playbooks de resposta a incidentes |

---

## 💰 Custo: $0/mês

| Componente | Tecnologia | Custo |
|------------|------------|-------|
| **LLM** | Ollama + llama3.2 | **$0** |
| **Linguagem** | Python 3.11+ | **$0** |
| **Monitoring** | Statistical (3-sigma, EWMA) | **$0** |
| **Notificações** | Slack webhook | **$0** |
| **Storage** | Sistema de arquivos | **$0** |

---

## 🚀 Quick Start

### 1. Setup (primeira vez)

```bash
cd ~/git/spot-render-teste-local

# O setup-local.sh já configura tudo automaticamente
bash setup-local.sh
```

### 2. Rodar um agente

```bash
cd ~/git/spot-render

# Ativar ambiente
source agents/venv/bin/activate

# Configurar LLM
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.2

# Rodar security scanner
python -m agents.main --agent security-scanner --repo ~/git/spot-render-teste-local

# Rodar documenter
python -m agents.main --agent documenter --repo ~/git/spot-render-teste-local
```

### 3. Rodar em loop autônomo

```bash
cd ~/git/spot-render-teste-local
bash scripts/run-autonomous.sh
```

---

## 📁 Estrutura

```
agents/
├── lib/
│   ├── llm.py              # Wrapper Ollama (gratuito)
│   ├── knowledge_base.py    # Aprendizado com incidentes
│   ├── approval_workflow.py # Aprovação humana
│   └── notifications.py     # Slack/PagerDuty
├── agents/
│   ├── security_scanner.py  # PRIO 1 - CVEs, secrets, IaC
│   ├── documenter.py        # PRIO 2 - README, API docs
│   ├── monitor.py          # PRIO 3 - Métricas, anomaly
│   ├── root_cause_analyzer.py # PRIO 4 - RCA 5 Whys
│   ├── alert_generator.py  # PRIO 5 - Prometheus rules
│   ├── capacity_planner.py # PRIO 6 - Forecasting
│   └── incident_responder.py # PRIO 7 - Playbooks
├── main.py                  # CLI entry point
├── requirements.txt        # Dependências ($0)
└── README.md
```

---

## ✅ Validação

```bash
# 1. Verificar Ollama
curl -s http://localhost:11434/api/version
# Esperado: {"version":"0.32.0"}

# 2. Verificar modelo
ollama list
# Esperado: NAME llama3.2

# 3. Testar LLM
curl -s http://localhost:11434/api/generate \
  -d '{"model":"llama3.2","prompt":"What is 2+2?","stream":false}'

# 4. Ver relatórios
ls -la ~/git/spot-render-teste-local/security-reports/
```

---

## 👤 Aprovação Humana

**Ações que SEMPRE requerem aprovação humana:**

| Ação | Risco |
|------|-------|
| `delete`, `drop`, `terminate` | CRITICAL |
| `deploy` em production | CRITICAL |
| `restart`, `rollback` | HIGH |
| `production_change` | CRITICAL |
| `security_change` | CRITICAL |

---

## 📚 Documentação Completa

Consulte [docs/AIOPS_AGENTS.md](./docs/AIOPS_AGENTS.md) para documentação técnica detalhada.

---

## 🔧 Configuração

```bash
# Variáveis de ambiente
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.2
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...  # opcional
```

---

*Zero custo. 100% gratuito. Roda offline.*

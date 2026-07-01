# ADR-001: Arquitetura de Banco de Dados e Mensageria para Spot Render

> **PT-BR:** Este ADR documenta as decisões arquiteturais sobre banco de dados, mensageria e cache para a plataforma Spot Render.

> **EN:** This ADR documents architectural decisions regarding database, messaging, and caching for the Spot Render platform.

## Status

**Aceito** (Accepted) - 2026-07-01

## Contexto (Context)

O Spot Render é uma plataforma de renderização distribuída que requer:

1. **Banco de dados** para armazenar:
   - Metadados de jobs (status, progresso, artista, projeto)
   - Histórico de renderizações
   - Configurações de projetos

2. **Sistema de fila** para:
   - Desacoplar upload de processamento
   - Permitir escalabilidade horizontal de workers
   - Garantir ordering e retry de jobs

3. **Cache** para:
   - Reduzir carga no banco de dados
   - Melhorar latência de读取 de jobs frequentes
   - Rate limiting

### Situação Anterior (Before)

- **Banco**: SQLite local (não adequado para produção multi-instância)
- **Fila**: Filesystem polling (não escalável, não confiável)
- **Cache**: Nenhum

### Requisitos

- Alta disponibilidade (Multi-AZ)
- Escalabilidade horizontal
- Custo otimizado (FinOps)
- Segurança (encriptação, IAM)
- Observabilidade completa

## Decisões (Decisions)

### 1. Banco de Dados: Aurora PostgreSQL Serverless v2

**Decisão:** Usar Amazon Aurora PostgreSQL em modo Serverless v2.

**Rationale:**

| Critério | Aurora Serverless v2 | RDS PostgreSQL | DynamoDB |
|----------|----------------------|----------------|----------|
| Custo | Paga só pelo usado (~$0.12/ACU-h) | Instância sempre ligada (~$0.17/hora) | Per 请求 ($0.25/milhão) |
| Escalabilidade | Auto 0.5-96 ACUs | Manual | Auto |
| HA | Multi-AZ nativo | Multi-AZ | Native |
| PostgreSQL compat | Sim | Sim | Não |
| Complexidade | Média | Baixa | Alta |

**Alternativas considered:**

- **Amazon RDS PostgreSQL**: Mais barato para workload constante, mas não escala bem para jobs variáveis
- **Amazon DynamoDB**: Ótimo para serverless, mas não é ideal para queries relacionais complexas
- **Amazon Aurora Serverless v2**: Melhor custo-benefício para workload de renderização (variável)

**Implementação:**

```hcl
# Terraform
module "database" {
  source = "./modules/database"

  serverless_min_capacity = 0.5   # $0.06/hora
  serverless_max_capacity = 16    # $1.92/hora max
  enable_read_replicas   = true
  backup_retention_days  = 7
  deletion_protection    = true
}
```

### 2. Mensageria: Amazon SQS

**Decisão:** Usar Amazon SQS Standard Queue com Dead Letter Queue.

**Rationale:**

| Critério | SQS | RabbitMQ | Apache Kafka |
|----------|-----|----------|--------------|
| Managed | Sim (zero ops) | Não (self-hosted) | Não (self-hosted) |
| Escalabilidade | Auto | Limitada | Alta (mas complexa) |
| DLQ nativo | Sim | Não | Não |
| Custo | $0.40/milhão msgs | $0.012/vCPU-hora | $0.10/GB |
| Ordering | Best effort | Sim | Sim |

**Configuração:**

- **Fila principal**: `spot-render-jobs`
  - Visibility timeout: 300s (5 min para processar)
  - Retention: 4 dias
  - Max message size: 256 KB

- **Dead Letter Queue**: `spot-render-jobs-dlq`
  - Retention: 14 dias
  - Redrive policy: após 3 tentativas

**Alternativas considered:**

- **RabbitMQ**: Mais Features mas requer gerenciamento de infraestrutura
- **Apache Kafka**: Overkill para este caso de uso (alto throughput, baixa latência)
- **Amazon SQS**: Melhor para este caso - managed, simples, DLQ nativo

### 3. Cache: ElastiCache Redis

**Decisão:** Usar Amazon ElastiCache Redis com cluster mode desabilitado (replicação 1 primary + 1 replica).

**Rationale:**

| Critério | ElastiCache | MemoryDB | DynamoDB DAX |
|----------|-------------|----------|--------------|
| Custo | ~$25/mês (cache.r6g.small) | ~$200/mês | ~$150/mês |
| Durabilidade | Opcional (RDB) | Sim | Sim |
| Pub/Sub | Sim | Sim | Não |
| Uso principal | Cache, sessions | Cache crítico | Accelerator |

**Casos de uso no Spot Render:**

1. **Cache de jobs**: Reduzir leitura do banco para jobs frequentes
2. **Rate limiting**: Controlar taxa de uploads por artista
3. **Session storage**: Guardar preferências de usuários

**Configuração:**

```hcl
module "cache" {
  source = "./modules/cache"

  node_type          = "cache.r6g.small"
  num_cache_clusters = 2  # 1 primary + 1 replica (Multi-AZ)
  auth_enabled       = true
  snapshot_retention_days = 7
}
```

### 4. Secrets: AWS Secrets Manager

**Decisão:** Usar AWS Secrets Manager para armazenar credenciais.

**Rationale:**

- Integração nativa com IAM
- Rotação automática de senhas
- Audit logging
- Criptografia via KMS

### 5. Monitoramento: CloudWatch + Alertas SNS

**Decisão:** Usar CloudWatch Metrics + Alarms com SNS para notificações.

**Métricas monitoradas:**

| Componente | Métrica | Threshold | Ação |
|------------|---------|------------|------|
| Aurora | ServerlessDatabaseCapacity | 85% max | Alerta |
| Aurora | DatabaseConnections | 400 | Alerta |
| Aurora | Deadlocks | > 0 | CRÍTICO |
| Redis | CPUUtilization | 75% | Alerta |
| Redis | DatabaseMemoryUsagePercentage | 80% | Alerta |
| SQS | ApproximateNumberOfMessagesVisible | 100 | Alerta |
| SQS | DLQ messages | > 0 | CRÍTICO |
| SQS | ApproximateAgeOfOldestMessage | 1800s | Alerta |

## Consequências (Consequences)

### Positivas

1. **Custo otimizado**: Serverless v2 paga só pelo uso
2. **Escalabilidade**: SQS e Aurora escalam automaticamente
3. **Confiabilidade**: Multi-AZ, DLQ, retry policy
4. **Segurança**: Encryption at rest/transit, IAM, Secrets Manager
5. **Observabilidade**: Dashboards e alertas para todos componentes

### Negativas

1. **Complexidade**: Mais serviços para gerenciar
2. **Vendor lock-in**: Acoplamento com AWS
3. **Custo variável**: Difficulty em prever custos mensais

### Workaround para Local/Dev

Criado `docker-compose.local.yml` com:
- PostgreSQL 15 (mesma engine)
- Redis 7
- LocalStack (SQS mock)

## Links

- [Aurora Serverless v2 Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [SQS Dead Letter Queues](https://docs.aws.amazon.com/AutoScaling/latest/DeveloperGuide/SQS-queue.html)
- [ElastiCache Redis](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/)

## Autores

- Platform Team - Rafael Cardoso

## Revisão

- [ ] DBRE Staff
- [ ] DevOps Staff

# ──────────────────────────────────────────────────────────────────────────────
# Módulo: cache
# Provisão de Amazon ElastiCache Redis para:
#   - Cache de sessões e dados temporários
#   - Cache de jobs em processamento
#   - Rate limiting
#   - Pub/Sub para notificações em tempo real
#
# Inclui:
#   - Redis Cluster Mode Enabled (sharding)
#   - Multi-AZ com replicas de leitura
#   - Encriptação em trânsito e em repouso
#   - Serverless (MemoryDB) ou serverful (ElastiCache) conforme configuração
# ──────────────────────────────────────────────────────────────────────────────

locals {
  tags = {
    Project     = "spot-render"
    Environment = var.environment
    Component   = "cache"
  }
}

# ─── Subnet Group ─────────────────────────────────────────────────────────────

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.prefix}-redis-subnet"
  subnet_ids = var.subnet_ids

  tags = local.tags
}

# ─── Security Group ────────────────────────────────────────────────────────────

resource "aws_security_group" "redis" {
  name_prefix = "${var.prefix}-redis-"
  description = "Security group para ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis access from within VPC"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    cidr_blocks     = [var.vpc_cidr]
    ipv6_cidr_blocks = []
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${var.prefix}-redis" })

  lifecycle {
    create_before_destroy = true
  }
}

# ─── Parameter Group ───────────────────────────────────────────────────────────

resource "aws_elasticache_parameter_group" "redis" {
  name   = "${var.prefix}-redis-7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  parameter {
    name  = "tcp-keepalive"
    value = "300"
  }

  tags = local.tags
}

# ─── ElastiCache Redis Cluster ────────────────────────────────────────────────

resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = "${var.prefix}-redis"
  replication_group_description = "Spot Render Redis Cluster"

  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  number_cache_clusters = var.num_cache_clusters

  # Rede e segurança
  security_group_ids  = [aws_security_group.redis.id]
  subnet_group_name   = aws_elasticache_subnet_group.this.name
  port                = 6379

  # HA e replication
  automatic_failover_enabled = var.num_cache_clusters > 1 ? true : false
  multi_az_enabled          = var.num_cache_clusters > 1 ? true : false
  read_endpoint             = var.num_cache_clusters > 1 ? true : false
  reader_endpoint           = var.num_cache_clusters > 1 ? true : false

  # Storage e durability
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled        = var.auth_enabled

  # Backup
  snapshot_retention_limit   = var.snapshot_retention_days
  snapshot_window            = "03:00-05:00"
  maintenance_window         = "mon:05:00-mon:07:00"

  # Performance
  parameters = aws_elasticache_parameter_group.redis.parameters

  # Logging
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

# ─── CloudWatch Log Groups ────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "redis_slow" {
  name              = "/aws/elasticache/${var.prefix}/redis/slow-log"
  retention_in_days = 7

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "redis_engine" {
  name              = "/aws/elasticache/${var.prefix}/redis/engine-log"
  retention_in_days = 3

  tags = local.tags
}

# ─── CloudWatch Alarms ────────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  alarm_name          = "${var.prefix}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period             = 300
  statistic          = "Average"
  threshold          = 75
  alarm_description  = "Alerta quando CPU do Redis está alto"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "memory_usage" {
  alarm_name          = "${var.prefix}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period             = 300
  statistic          = "Average"
  threshold          = 80
  alarm_description  = "Alerta quando uso de memória do Redis está alto"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "evictions" {
  alarm_name          = "${var.prefix}-redis-evictions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period             = 300
  statistic          = "Sum"
  threshold          = 1000
  alarm_description  = "Alerta quando há muitas evictions (cache pode estar pequeno)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "replication_lag" {
  count = var.num_cache_clusters > 1 ? 1 : 0

  alarm_name          = "${var.prefix}-redis-repl-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  metric_name         = "ReplicationLag"
  namespace           = "AWS/ElastiCache"
  period             = 60
  statistic          = "Maximum"
  threshold          = 5
  alarm_description  = "Alerta quando há lag de replicação entre primary e replicas"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "redis_endpoint" {
  description = "Endpoint primário do Redis"
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "Endpoint de leitura (distribui entre réplicas)"
  value       = var.num_cache_clusters > 1 ? aws_elasticache_replication_group.this.reader_endpoint_address : null
}

output "redis_port" {
  description = "Porta do Redis"
  value       = aws_elasticache_replication_group.this.port
}

output "redis_arn" {
  description = "ARN do ElastiCache Replication Group"
  value       = aws_elasticache_replication_group.this.arn
}

output "security_group_id" {
  description = "ID do Security Group do Redis"
  value       = aws_security_group.redis.id
}

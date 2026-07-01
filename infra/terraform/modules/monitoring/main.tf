# ──────────────────────────────────────────────────────────────────────────────
# Módulo: monitoring
# CloudWatch Dashboards e Alertas para Spot Render
#
# Inclui:
#   - Dashboard principal com métricas de DB, SQS e Redis
#   - Alertas para disponibilidade, performance e custos
#   - SNS topics para notificação
# ──────────────────────────────────────────────────────────────────────────────

locals {
  tags = {
    Project     = "spot-render"
    Environment = var.environment
    Component   = "monitoring"
  }
}

# ─── SNS Topic para Alertas ───────────────────────────────────────────────────

resource "aws_sns_topic" "alerts" {
  name = "${var.prefix}-alerts-${var.environment}"

  tags = local.tags
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alert_email != null ? 1 : 0

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ─── Dashboard Principal ───────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.prefix}-dashboard-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      # ─── Aurora PostgreSQL ───────────────────────────────────────────────
      {
        type = "metric"
        properties = {
          title = "Aurora CPU/ACU Utilization"
          region = var.aws_region
          stat = "Average"
          period = 300
          metrics = [
            ["AWS/RDS", "ServerlessDatabaseCapacity", "DBClusterIdentifier", "${var.prefix}-aurora", {"stat" = "Maximum"}],
            [".", "ServerlessDatabaseCapacity", ".", ".", {"stat" = "Minimum"}],
          ]
          yAxis = { left = { min = 0, max = 96 } }
        }
      },
      {
        type = "metric"
        properties = {
          title = "Aurora Connections"
          region = var.aws_region
          stat = "Average"
          period = 300
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBClusterIdentifier", "${var.prefix}-aurora"],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title = "Aurora Deadlocks"
          region = var.aws_region
          stat = "Sum"
          period = 60
          metrics = [
            ["AWS/RDS", "Deadlocks", "DBClusterIdentifier", "${var.prefix}-aurora"],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title = "Aurora Backup Retention (days)"
          region = var.aws_region
          stat = "Minimum"
          period = 86400
          metrics = [
            ["AWS/RDS", "BackupRetention", "DBClusterIdentifier", "${var.prefix}-aurora"],
          ]
        }
      },
      # ─── ElastiCache Redis ─────────────────────────────────────────────
      {
        type = "metric"
        properties = {
          title = "Redis CPU Utilization"
          region = var.aws_region
          stat = "Average"
          period = 300
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "ReplicationGroupId", "${var.prefix}-redis"],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title = "Redis Memory Usage %"
          region = var.aws_region
          stat = "Average"
          period = 300
          metrics = [
            ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", "ReplicationGroupId", "${var.prefix}-redis"],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title = "Redis Evictions"
          region = var.aws_region
          stat = "Sum"
          period = 300
          metrics = [
            ["AWS/ElastiCache", "Evictions", "ReplicationGroupId", "${var.prefix}-redis"],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title = "Redis Replication Lag (s)"
          region = var.aws_region
          stat = "Maximum"
          period = 60
          metrics = [
            ["AWS/ElastiCache", "ReplicationLag", "ReplicationGroupId", "${var.prefix}-redis"],
          ]
        }
      },
      # ─── SQS Queue ───────────────────────────────────────────────────────
      {
        type = "metric"
        properties = {
          title = "SQS Jobs Queue Depth"
          region = var.aws_region
          stat = "Maximum"
          period = 300
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "spot-render-jobs"],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title = "SQS DLQ Messages"
          region = var.aws_region
          stat = "Sum"
          period = 300
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "spot-render-jobs-dlq"],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title = "SQS Oldest Message Age (s)"
          region = var.aws_region
          stat = "Maximum"
          period = 300
          metrics = [
            ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", "spot-render-jobs"],
          ]
        }
      },
      # ─── FinOps/Custo ───────────────────────────────────────────────────
      {
        type = "metric"
        properties = {
          title = "Estimated DB Cost ($/day)"
          region = var.aws_region
          stat = "Average"
          period = 86400
          metrics = [
            ["AWS/RDS", "ServerlessDatabaseCapacity", "DBClusterIdentifier", "${var.prefix}-aurora", {"stat" = "Maximum"}],
            [".", ".", ".", ".", { "math" = "MAX() * 0.12" }],  # $0.12/ACU-hour
          ]
        }
      },
    ]
  })
}

# ─── Alarme: Aurora Serverless ACU Alta ──────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "aurora_acu_high" {
  alarm_name          = "${var.prefix}-aurora-acu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  metric_name         = "ServerlessDatabaseCapacity"
  namespace           = "AWS/RDS"
  period             = 300
  statistic          = "Maximum"
  threshold          = var.serverless_max_capacity * 0.85
  alarm_description  = "Aurora Serverless ACU está usando 85% ou mais da capacidade máxima"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = "${var.prefix}-aurora"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Alarme: Conexões DB Altas ───────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "aurora_connections_high" {
  alarm_name          = "${var.prefix}-aurora-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period             = 300
  statistic          = "Average"
  threshold          = 400
  alarm_description  = "Número de conexões ao banco está alto"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = "${var.prefix}-aurora"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Alarme: Deadlocks ────────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "aurora_deadlocks" {
  alarm_name          = "${var.prefix}-aurora-deadlocks"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  metric_name         = "Deadlocks"
  namespace           = "AWS/RDS"
  period             = 60
  statistic          = "Sum"
  threshold          = 1
  alarm_description  = "Deadlock detectado no banco de dados"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = "${var.prefix}-aurora"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Alarme: Redis CPU Alto ──────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "redis_cpu_high" {
  alarm_name          = "${var.prefix}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period             = 300
  statistic          = "Average"
  threshold          = 75
  alarm_description  = "CPU do Redis está alto"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = "${var.prefix}-redis"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Alarme: Redis Memory Alto ────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "redis_memory_high" {
  alarm_name          = "${var.prefix}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period             = 300
  statistic          = "Average"
  threshold          = 80
  alarm_description  = "Uso de memória do Redis está em 80% ou mais"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = "${var.prefix}-redis"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Alarme: SQS Queue Depth Alta ───────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "sqs_queue_depth_high" {
  alarm_name          = "${var.prefix}-sqs-queue-depth-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period             = 300
  statistic          = "Maximum"
  threshold          = var.sqs_queue_depth_threshold
  alarm_description  = "Fila de jobs tem muitas mensagens pendentes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = "spot-render-jobs"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Alarme: DLQ com Mensagens ────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "sqs_dlq_has_messages" {
  alarm_name          = "${var.prefix}-sqs-dlq-has-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period             = 300
  statistic          = "Sum"
  threshold          = 1
  alarm_description  = "Dead Letter Queue tem mensagens - jobs falharam"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = "spot-render-jobs-dlq"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Alarme: Jobs Antigos na Fila ───────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "sqs_oldest_message" {
  alarm_name          = "${var.prefix}-sqs-oldest-message"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period             = 300
  statistic          = "Maximum"
  threshold          = 1800  # 30 min
  alarm_description  = "Jobs estão esperando mais de 30 minutos na fila"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = "spot-render-jobs"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions   = [aws_sns_topic.alerts.arn]

  tags = local.tags
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "sns_topic_arn" {
  description = "ARN do SNS Topic para alertas"
  value       = aws_sns_topic.alerts.arn
}

output "dashboard_url" {
  description = "URL do CloudWatch Dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${var.prefix}-dashboard-${var.environment}"
}

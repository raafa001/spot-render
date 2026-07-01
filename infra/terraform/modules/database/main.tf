# ──────────────────────────────────────────────────────────────────────────────
# Módulo: database
# Provisão de Amazon Aurora PostgreSQL Serverless v2 para:
#   - Banco de dados principal da API (jobs, filas, metadata)
#   - Alta disponibilidade com Multi-AZ
#   - Read replicas para escalar leitura
#   - Backups automatizados com PITR
#   - Performance Insights para tuning
#
# Serverless v2: escala automaticamente de 0.5 a 96 ACUs
# Custo estimado: ~$0.12/ACU-hora vs $0.17/hora para db.r6g.large
# ──────────────────────────────────────────────────────────────────────────────

locals {
  tags = {
    Project     = "spot-render"
    Environment = var.environment
    Component   = "database"
  }
}

# ─── Subnet Group ─────────────────────────────────────────────────────────────

resource "aws_rds_subnet_group" "this" {
  name       = "${var.prefix}-aurora-subnet"
  subnet_ids = var.subnet_ids

  tags = local.tags
}

# ─── Security Group ───────────────────────────────────────────────────────────

resource "aws_security_group" "db" {
  name_prefix = "${var.prefix}-aurora-"
  description = "Security group para Aurora PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${var.prefix}-aurora" })

  lifecycle {
    create_before_destroy = true
  }
}

# ─── Cluster Parameter Group ───────────────────────────────────────────────────

resource "aws_rds_cluster_parameter_group" "aurora_postgres" {
  name   = "${var.prefix}-aurora-postgres"
  family = "aurora-postgresql15"

  parameter {
    name  = "max_connections"
    value = "500"
  }

  parameter {
    name  = "shared_buffers"
    value = "256MB"
  }

  parameter {
    name  = "work_mem"
    value = "16MB"
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "512MB"
  }

  parameter {
    name  = "effective_cache_size"
    value = "2GB"
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "rds.log_retention_period"
    value = "259200" # 3 dias em segundos
  }

  parameter {
    name  = "autovacuum_max_workers"
    value = "4"
  }

  parameter {
    name  = "autovacuum_naptime"
    value = "10"
  }

  tags = local.tags
}

# ─── Aurora Cluster ───────────────────────────────────────────────────────────

resource "aws_rds_cluster" "this" {
  cluster_identifier              = "${var.prefix}-aurora"
  engine                          = "aurora-postgresql"
  engine_version                  = var.engine_version
  engine_mode                     = "provisioned" # Serverless usa "serverless", mas preferimos provisioned para produção
  database_name                   = var.db_name
  master_username                 = var.username
  master_password                 = var.password
  port                            = 5432

  # Rede
  vpc_security_group_ids  = [aws_security_group.db.id]
  db_subnet_group_name    = aws_rds_subnet_group.this.name

  # Storage
  storage_encrypted       = true
  kms_key_id             = var.kms_key_id

  # Backup e Recovery
  backup_retention_period = var.backup_retention_days
  preferred_backup_window = "03:00-05:00"
  preferred_maintenance_window = "mon:05:00-mon:07:00"
  deletion_protection     = var.deletion_protection
  copy_tags_to_snapshot   = true

  # Performance e Monitoring
  monitoring_interval     = var.enable_monitoring ? 60 : 0
  performance_insights_enabled = var.enable_monitoring
  performance_insights_retention_period = var.enable_monitoring ? 731 : null # 2 anos

  # Serverless v2 Configuration
  serverlessv2_scaling_configuration {
    min_capacity = var.serverless_min_capacity
    max_capacity = var.serverless_max_capacity
  }

  # Logs
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  # Global Database (opcional - para DR entre regiões)
  global_cluster_identifier = var.enable_global_db ? "${var.prefix}-global" : null

  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.prefix}-final-snapshot" : null

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

# ─── Writer Instance (Serverless v2) ─────────────────────────────────────────

resource "aws_rds_cluster_instance" "writer" {
  count = 1

  identifier         = "${var.prefix}-aurora-writer"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class    = "db.serverless" # Serverless v2 usa classe especial
  engine            = aws_rds_cluster.this.engine
  engine_version    = aws_rds_cluster.this.engine_version

  publicly_accessible = false
  promotion_tier     = 0

  # Performance Insights via IAM role (criado automaticamente pelo console)
  performance_insights_enabled = var.enable_monitoring
  monitoring_interval         = var.enable_monitoring ? 60 : 0

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

# ─── Reader Instances (opcional para scaling de leitura) ──────────────────────

resource "aws_rds_cluster_instance" "readers" {
  count = var.enable_read_replicas ? var.num_read_replicas : 0

  identifier         = "${var.prefix}-aurora-reader-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine            = aws_rds_cluster.this.engine
  engine_version    = aws_rds_cluster.this.engine_version

  publicly_accessible = false
  promotion_tier     = 1 # Nunca promove automaticamente

  performance_insights_enabled = var.enable_monitoring
  monitoring_interval         = var.enable_monitoring ? 60 : 0

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

# ─── Global Database (opcional - DR entre regiões) ─────────────────────────────

resource "aws_rds_global_cluster" "this" {
  count = var.enable_global_db ? 1 : 0

  global_cluster_identifier    = "${var.prefix}-global"
  force_destroy                = false
  engine                       = "aurora-postgresql"
  engine_version               = var.engine_version
  database_name                = var.db_name
  master_username             = var.username
  master_password             = var.password
  storage_encrypted           = true
  kms_key_id                  = var.kms_key_id

  lifecycle {
    create_before_destroy = true
  }
}

# ─── CloudWatch Alarms ────────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  alarm_name          = "${var.prefix}-aurora-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  metric_name         = "ServerlessDatabaseCapacity"
  namespace           = "AWS/RDS"
  period             = 300
  statistic          = "Average"
  threshold          = 80 # 80% de utilização de ACUs
  alarm_description  = "Alerta quando CPU do Aurora Serverless está alto"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "connections" {
  alarm_name          = "${var.prefix}-aurora-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period             = 300
  statistic          = "Average"
  threshold          = 400 # Limite مناسب para Serverless
  alarm_description  = "Alerta quando número de conexões está alto"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "deadlocks" {
  alarm_name          = "${var.prefix}-aurora-deadlocks"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  metric_name         = "Deadlocks"
  namespace           = "AWS/RDS"
  period             = 60
  statistic          = "Sum"
  threshold          = 1
  alarm_description  = "Alerta quando há deadlocks no banco"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "backup_retention" {
  alarm_name          = "${var.prefix}-aurora-backup-retention"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  metric_name         = "BackupRetention"
  namespace           = "AWS/RDS"
  period             = 86400 # 1 dia
  statistic          = "Minimum"
  threshold          = var.backup_retention_days
  alarm_description  = "Alerta se retenção de backup está abaixo do configured"
  treat_missing_data  = "breaching"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "ACU_utilization" {
  alarm_name          = "${var.prefix}-aurora-acu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  metric_name         = "ServerlessDatabaseCapacity"
  namespace           = "AWS/RDS"
  period             = 300
  statistic          = "Maximum"
  threshold          = var.serverless_max_capacity * 0.85
  alarm_description  = "Alerta quando utilização de ACUs está próxima do máximo (85%)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.this.id
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "cluster_endpoint" {
  description = "Endpoint do cluster (writer)"
  value       = aws_rds_cluster.this.endpoint
}

output "cluster_reader_endpoint" {
  description = "Endpoint de leitura (distribui entre réplicas)"
  value       = aws_rds_cluster.this.reader_endpoint
}

output "cluster_arn" {
  description = "ARN do cluster"
  value       = aws_rds_cluster.this.arn
}

output "cluster_id" {
  description = "ID do cluster"
  value       = aws_rds_cluster.this.id
}

output "security_group_id" {
  description = "ID do Security Group"
  value       = aws_security_group.db.id
}

output "global_cluster_arn" {
  description = "ARN do Global Cluster (se habilitado)"
  value       = try(aws_rds_global_cluster.this[0].arn, null)
}

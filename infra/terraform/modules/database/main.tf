locals {
  tags = {
    Environment = "database"
    Project     = "spot-render"
  }
}

resource "aws_security_group" "db" {
  count = var.create_rds && length(var.vpc_security_group_ids) == 0 ? 1 : 0

  name_prefix = "spot-render-db-"
  description = "Acesso interno ao PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.vpc_cidr != null ? [var.vpc_cidr] : ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "spot-render-db" })

  lifecycle {
    precondition {
      condition     = var.vpc_id != null
      error_message = "vpc_id deve ser fornecido quando nenhum security group externo é informado."
    }
  }
}

locals {
  effective_security_groups = length(var.vpc_security_group_ids) > 0 ? var.vpc_security_group_ids : aws_security_group.db[*].id
}

resource "aws_db_subnet_group" "this" {
  count      = var.create_rds ? 1 : 0
  name       = "spot-render-db"
  subnet_ids = var.subnet_ids

  tags = local.tags
}

resource "aws_db_parameter_group" "postgres" {
  count  = var.create_rds ? 1 : 0
  name   = "spot-render-postgres"
  family = "postgres${replace(var.engine_version, ".", "")}" # ex.: 15 -> postgres15

  parameter {
    name  = "max_connections"
    value = "500"
  }

  parameter {
    name  = "shared_buffers"
    value = "256MB"
  }

  tags = local.tags
}

resource "aws_db_instance" "this" {
  count                                 = var.create_rds ? 1 : 0
  identifier                            = "spot-render-db"
  allocated_storage                     = var.allocated_storage
  max_allocated_storage                 = var.allocated_storage + 200
  storage_encrypted                     = true
  engine                                = "postgres"
  engine_version                        = var.engine_version
  instance_class                        = var.instance_class
  db_name                               = var.db_name
  username                              = var.username
  password                              = var.password
  port                                  = 5432
  multi_az                              = true
  auto_minor_version_upgrade            = true
  backup_retention_period               = 7
  deletion_protection                   = true
  copy_tags_to_snapshot                 = true
  parameter_group_name                  = aws_db_parameter_group.postgres[0].name
  db_subnet_group_name                  = aws_db_subnet_group.this[0].name
  vpc_security_group_ids                = local.effective_security_groups
  publicly_accessible                   = false
  monitoring_interval                   = var.enable_monitoring ? 60 : 0
  performance_insights_enabled          = var.enable_monitoring
  performance_insights_retention_period = var.enable_monitoring ? 7 : null
  ca_cert_identifier                    = var.ca_cert_identifier

  tags = local.tags
}

# -----------------------------
# PostgreSQL local no cluster
# -----------------------------

resource "kubernetes_namespace" "local" {
  count = var.create_local_statefulset ? 1 : 0
  metadata {
    name = var.local_namespace
    labels = {
      "spot-render.io/component" = "database"
    }
  }
}

resource "kubernetes_secret" "postgres" {
  count = var.create_local_statefulset ? 1 : 0
  metadata {
    name      = "postgres-admin"
    namespace = var.local_namespace
  }

  data = {
    username = base64encode(var.username)
    password = base64encode(var.password)
    database = base64encode(var.db_name)
  }
}

resource "kubernetes_persistent_volume_claim" "postgres" {
  count = var.create_local_statefulset ? 1 : 0

  metadata {
    name      = "postgres-data"
    namespace = var.local_namespace
  }

  spec {
    access_modes = ["ReadWriteOnce"]

    resources {
      requests = {
        storage = var.local_storage_size
      }
    }

    storage_class_name = var.storage_class_name
  }
}

resource "kubernetes_stateful_set" "postgres" {
  count = var.create_local_statefulset ? 1 : 0

  metadata {
    name      = "postgres"
    namespace = var.local_namespace
    labels = {
      app = "postgres"
    }
  }

  spec {
    service_name = "postgres"
    replicas     = 1

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    template {
      metadata {
        labels = {
          app = "postgres"
        }
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:${var.engine_version}"

          env {
            name = "POSTGRES_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.postgres[0].metadata[0].name
                key  = "username"
              }
            }
          }

          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.postgres[0].metadata[0].name
                key  = "password"
              }
            }
          }

          env {
            name = "POSTGRES_DB"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.postgres[0].metadata[0].name
                key  = "database"
              }
            }
          }

          port {
            name           = "postgres"
            container_port = 5432
          }

          liveness_probe {
            initial_delay_seconds = 30
            period_seconds        = 10
            tcp_socket {
              port = "postgres"
            }
          }

          readiness_probe {
            initial_delay_seconds = 15
            period_seconds        = 10
            exec {
              command = ["/bin/sh", "-c", "pg_isready -U $POSTGRES_USER -d $POSTGRES_DB"]
            }
          }

          resources {
            limits = {
              cpu    = "1"
              memory = "2Gi"
            }
            requests = {
              cpu    = "500m"
              memory = "1Gi"
            }
          }

          volume_mount {
            name       = "data"
            mount_path = "/var/lib/postgresql/data"
          }
        }

        volume {
          name = "data"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.postgres[0].metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "postgres" {
  count = var.create_local_statefulset ? 1 : 0

  metadata {
    name      = "postgres"
    namespace = var.local_namespace
  }

  spec {
    selector = {
      app = "postgres"
    }

    port {
      name        = "postgres"
      port        = 5432
      target_port = 5432
    }
  }
}

output "rds_endpoint" {
  description = "Endpoint do RDS."
  value       = try(aws_db_instance.this[0].endpoint, null)
}

output "secret_arn" {
  description = "Secret associado (caso exista)."
  value       = null
}

output "local_service_name" {
  description = "Nome do Service expondo o PostgreSQL local."
  value       = try(kubernetes_service.postgres[0].metadata[0].name, null)
}

output "local_pvc_name" {
  description = "PVC usado pelo PostgreSQL local."
  value       = try(kubernetes_persistent_volume_claim.postgres[0].metadata[0].name, null)
}

# ──────────────────────────────────────────────────────────────────────────────
# Módulo: messaging
# Provisão de Amazon SQS para fila de jobs de renderização.
# Inclui:
#   - Fila principal (spot-render-jobs)
#   - Dead Letter Queue (DLQ) para jobs com falha
#   - Retry policy com backoff exponencial
#   - Server-side encryption (SSE)
#   - CloudWatch alarms para profundidade da fila
# ──────────────────────────────────────────────────────────────────────────────

locals {
  tags = {
    Project     = "spot-render"
    Environment = var.environment
    Component   = "messaging"
  }
}

# ─── Dead Letter Queue ────────────────────────────────────────────────────────

resource "aws_sqs_queue" "dlq" {
  name                              = "${var.prefix}-jobs-dlq"
  fifo_queue                        = false
  max_message_size                  = 262144 # 256 KiB
  message_retention_seconds         = 1209600 # 14 dias (máximo)
  visibility_timeout_seconds        = 60
  receive_wait_time_seconds         = 20 # Long polling
  sqs_managed_sse_enabled          = true

  tags = local.tags
}

# ─── Fila Principal de Jobs ───────────────────────────────────────────────────

resource "aws_sqs_queue" "jobs" {
  name                              = "${var.prefix}-jobs"
  fifo_queue                        = false
  max_message_size                  = 262144
  message_retention_seconds         = 345600 # 4 dias
  visibility_timeout_seconds        = 300   # 5 min para processar
  receive_wait_time_seconds         = 20
  redrive_policy                    = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3 # Após 3 tentativas, vai para DLQ
  })
  sqs_managed_sse_enabled          = true

  tags = local.tags
}

# ─── Policy para permitir apenas IDs de mensagem específicos ───────────────────

data "aws_iam_policy_document" "jobs_queue_policy" {
  statement {
    sid    = "AllowOnlyFromVPC"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
    ]

    resources = [
      aws_sqs_queue.jobs.arn,
      aws_sqs_queue.dlq.arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceVpce"
      values   = var.allowed_vpce_ids
    }
  }

  statement {
    sid    = "AllowEncryptedAccess"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = ["sqs:*"]
    resources = [
      aws_sqs_queue.jobs.arn,
      aws_sqs_queue.dlq.arn,
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sqs_queue_policy" "jobs" {
  queue_url = aws_sqs_queue.jobs.id
  policy    = data.aws_iam_policy_document.jobs_queue_policy.json
}

resource "aws_sqs_queue_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id
  policy    = data.aws_iam_policy_document.jobs_queue_policy.json
}

# ─── CloudWatch Alarms ────────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "jobs_queue_depth" {
  alarm_name          = "${var.prefix}-jobs-queue-depth-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period             = 300 # 5 min
  statistic          = "Average"
  threshold          = var.queue_depth_alarm_threshold
  alarm_description  = "Alerta quando há muitos jobs pendentes na fila"
  treat_missing_data = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.jobs.name
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.prefix}-dlq-has-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period             = 60
  statistic          = "Sum"
  threshold          = 1
  alarm_description  = "Alerta quando há mensagens na DLQ (jobs com falha)"
  treat_missing_data = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "jobs_oldest_message" {
  alarm_name          = "${var.prefix}-jobs-oldest-message"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period             = 300
  statistic          = "Maximum"
  threshold          = 1800 # 30 min
  alarm_description  = "Alerta quando há mensagens esperando mais de 30 min"
  treat_missing_data = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.jobs.name
  }

  alarm_actions = var.alert_topic_arns
  ok_actions   = var.alert_topic_arns

  tags = local.tags
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "jobs_queue_url" {
  description = "URL da fila principal de jobs"
  value       = aws_sqs_queue.jobs.url
}

output "jobs_queue_arn" {
  description = "ARN da fila principal de jobs"
  value       = aws_sqs_queue.jobs.arn
}

output "dlq_url" {
  description = "URL da Dead Letter Queue"
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "ARN da Dead Letter Queue"
  value       = aws_sqs_queue.dlq.arn
}

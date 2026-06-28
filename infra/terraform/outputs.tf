output "state_bucket" {
  description = "Bucket configurado para armazenar o state remoto."
  value       = var.tf_state_bucket
}

output "environment" {
  description = "Ambiente atualmente configurado."
  value       = var.environment
}

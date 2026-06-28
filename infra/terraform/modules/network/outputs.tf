locals {
  vpc_id_output = try(aws_vpc.this[0].id, null)
  private_ids   = try(aws_subnet.private[*].id, [])
  public_ids    = try(aws_subnet.public[*].id, [])
  nat_ids       = try(aws_nat_gateway.this[*].id, [])
}

output "vpc_id" {
  value       = local.vpc_id_output
  description = "ID da VPC criada."
}

output "private_subnet_ids" {
  value       = local.private_ids
  description = "IDs das subnets privadas."
}

output "public_subnet_ids" {
  value       = local.public_ids
  description = "IDs das subnets públicas."
}

output "nat_gateway_ids" {
  value       = local.nat_ids
  description = "IDs dos NAT Gateways."
}

output "database_subnet_ids" {
  value       = local.private_ids
  description = "Subnets usadas pelo RDS."
}

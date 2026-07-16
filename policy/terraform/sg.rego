package terraform.security

deny[msg] {
  resource := input.resource_changes[_]
  resource.change.after != null
  resource.type == "aws_security_group"

  ingress := resource.change.after.ingress[_]
  cidr := ingress.cidr_blocks[_]
  cidr == "0.0.0.0/0"

  ssh_from := ingress.from_port
  ssh_to   := ingress.to_port
  ssh_from <= 22
  ssh_to   >= 22

  msg := sprintf("Security group %s expõe SSH (porta 22) para a internet", [resource.address])
}

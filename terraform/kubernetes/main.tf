module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.0.0"

  cluster_name    = "spot-render"
  cluster_version = "1.27"

  vpc_id     = aws_vpc.spot-render-ntw.id
  subnets    = [aws_subnet.spot-render-subnet.id]

  tags = {
    Environment = "dev"          # Ambiente de desenvolvimento
    Project     = "renderizacao" # Nome do projeto
    AutoOff     = "true"         # Indica se deve ser desligado automaticamente
  }

  node_groups = {
    spot-nodes = {
      desired_capacity = 2
      max_capacity     = 3
      min_capacity     = 1
      instance_type    = "t3.medium"
      k8s_version      = "1.27"
      capacity_type    = "SPOT"
      update_policy    = "Auto"
      tags = {
        Environment = "dev"
        Project     = "renderizacao"
        AutoOff     = "true"
      }
    }
  }
}

resource "aws_vpc" "spot-render-ntw" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "spot-render-subnet" {
  vpc_id      = aws_vpc.spot-render-ntw.id
  cidr_block = "10.0.1.0/24"
}

resource "aws_security_group" "eks_cluster_sg" {
  name_prefix = "eks-cluster-sg-"
  vpc_id      = aws_vpc.spot-render-ntw.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTPS access to EKS API"
  }

  ingress {
    from_port   = 3000 # Porta padrão do Grafana
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow access to Grafana"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "eks-cluster-security-group"
    Environment = "dev"
    Project     = "renderizacao"
    AutoOff     = "true"
  }
}

output "vpc_id" {
  value = aws_vpc.spot-render-ntw.id
}

output "subnet_ids" {
  value = [aws_subnet.spot-render-subnet.id]
}

output "eks_cluster_security_group_id" {
  value = aws_security_group.eks_cluster_sg.id
}
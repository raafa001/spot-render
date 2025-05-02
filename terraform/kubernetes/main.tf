module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.36.0" # **Versão mais recente do módulo EKS**

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version
  vpc_id          = var.vpc_id
  subnet_ids      = var.subnets
  tags            = var.tags
  eks_managed_node_groups = var.eks_node_groups
}
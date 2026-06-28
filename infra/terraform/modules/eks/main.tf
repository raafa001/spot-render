locals {
  tags = {
    Environment = "eks"
    Project     = "spot-render"
  }
}

resource "aws_iam_role" "cluster" {
  count = var.create ? 1 : 0
  name  = "spot-render-eks-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSClusterPolicy" {
  count      = var.create ? 1 : 0
  role       = aws_iam_role.cluster[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSServicePolicy" {
  count      = var.create ? 1 : 0
  role       = aws_iam_role.cluster[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSServicePolicy"
}

resource "aws_security_group" "cluster" {
  count       = var.create ? 1 : 0
  name        = "spot-render-eks-cluster"
  description = "SG do plano de controle do EKS"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "spot-render-eks" })
}

resource "aws_eks_cluster" "this" {
  count    = var.create ? 1 : 0
  name     = var.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster[0].arn

  vpc_config {
    subnet_ids              = var.subnet_ids
    security_group_ids      = [aws_security_group.cluster[0].id]
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = ["0.0.0.0/0"]
  }

  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  tags = local.tags
}

resource "aws_iam_role" "node" {
  count = var.create ? 1 : 0
  name  = "spot-render-eks-node"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  count      = var.create ? 1 : 0
  role       = aws_iam_role.node[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  count      = var.create ? 1 : 0
  role       = aws_iam_role.node[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "node_ecr" {
  count      = var.create ? 1 : 0
  role       = aws_iam_role.node[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_eks_node_group" "gpu" {
  count = var.create ? 1 : 0

  cluster_name    = aws_eks_cluster.this[0].name
  node_group_name = "gpu-render"
  node_role_arn   = aws_iam_role.node[0].arn
  subnet_ids      = var.subnet_ids

  scaling_config {
    desired_size = var.desired_size
    max_size     = var.max_size
    min_size     = var.min_size
  }

  instance_types = var.gpu_instance_types
  ami_type       = "AL2_x86_64_GPU"
  capacity_type  = "ON_DEMAND"

  labels = {
    workload                     = "render"
    gpu                          = "true"
    "spot-render.io/gpu-capable" = "true"
  }

  taint {
    key    = "nvidia.com/gpu"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  update_config {
    max_unavailable = 1
  }

  timeouts {
    create = "60m"
    update = "60m"
    delete = "30m"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr
  ]
}

resource "aws_eks_addon" "kube_proxy" {
  count        = var.create ? 1 : 0
  cluster_name = aws_eks_cluster.this[0].name
  addon_name   = "kube-proxy"
}

resource "aws_eks_addon" "vpc_cni" {
  count        = var.create ? 1 : 0
  cluster_name = aws_eks_cluster.this[0].name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "coredns" {
  count        = var.create ? 1 : 0
  cluster_name = aws_eks_cluster.this[0].name
  addon_name   = "coredns"
}

data "aws_eks_cluster" "auth" {
  count = var.create ? 1 : 0
  name  = aws_eks_cluster.this[0].name

  depends_on = [aws_eks_cluster.this]
}

data "aws_eks_cluster_auth" "this" {
  count = var.create ? 1 : 0
  name  = aws_eks_cluster.this[0].name
}

data "tls_certificate" "eks" {
  count = var.create ? 1 : 0
  url   = aws_eks_cluster.this[0].identity[0].oidc[0].issuer
}

# IRSA - provedor OIDC necessário para Argo Rollouts, External Secrets, etc.
resource "aws_iam_openid_connect_provider" "eks" {
  count = var.create ? 1 : 0
  url   = data.aws_eks_cluster.auth[0].identity[0].oidc[0].issuer

  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks[0].certificates[0].sha1_fingerprint]
}

# IAM para o Karpenter Controller
resource "aws_iam_role" "karpenter_controller" {
  count = var.create && var.enable_karpenter ? 1 : 0
  name  = "spot-render-karpenter-controller"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks[0].arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(data.aws_eks_cluster.auth[0].identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:${var.karpenter_namespace}:karpenter"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "karpenter_controller" {
  count = var.create && var.enable_karpenter ? 1 : 0
  role  = aws_iam_role.karpenter_controller[0].id

  policy = file("${path.module}/policies/karpenter-controller.json")
}

resource "aws_sqs_queue" "karpenter_interrupts" {
  count = var.create && var.enable_karpenter ? 1 : 0
  name  = "spot-render-karpenter-interrupts"

  sqs_managed_sse_enabled = true
}

resource "aws_cloudwatch_event_rule" "spot_interrupts" {
  count = var.create && var.enable_karpenter ? 1 : 0
  name  = "spot-render-interrupts"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })
}

resource "aws_cloudwatch_event_target" "spot_interrupts" {
  count = var.create && var.enable_karpenter ? 1 : 0
  rule  = aws_cloudwatch_event_rule.spot_interrupts[0].name
  arn   = aws_sqs_queue.karpenter_interrupts[0].arn
}

resource "aws_iam_role" "karpenter_instance" {
  count = var.create && var.enable_karpenter ? 1 : 0
  name  = "spot-render-karpenter-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "karpenter_instance_worker" {
  count      = var.create && var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "karpenter_instance_cni" {
  count      = var.create && var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "karpenter_instance_registry" {
  count      = var.create && var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
}

resource "aws_iam_instance_profile" "karpenter" {
  count = var.create && var.enable_karpenter ? 1 : 0
  name  = "spot-render-karpenter-instance"
  role  = aws_iam_role.karpenter_instance[0].name
}

# Contas administrativas - configuradas via Access Entries.
resource "aws_eks_access_entry" "admins" {
  count         = var.create ? length(var.aws_auth_admin_arns) : 0
  cluster_name  = aws_eks_cluster.this[0].name
  principal_arn = var.aws_auth_admin_arns[count.index]
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "admins" {
  count         = var.create ? length(var.aws_auth_admin_arns) : 0
  cluster_name  = aws_eks_cluster.this[0].name
  principal_arn = var.aws_auth_admin_arns[count.index]
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

output "cluster_name" {
  value       = try(aws_eks_cluster.this[0].name, null)
  description = "Nome do cluster."
}

output "cluster_endpoint" {
  value       = try(aws_eks_cluster.this[0].endpoint, null)
  description = "Endpoint da API do cluster."
}

output "cluster_certificate" {
  value       = try(aws_eks_cluster.this[0].certificate_authority[0].data, null)
  description = "CA do cluster."
}

output "oidc_provider_arn" {
  value       = try(aws_iam_openid_connect_provider.eks[0].arn, null)
  description = "ARN do provedor OIDC (IRSA)."
}

output "node_group_arn" {
  value       = try(aws_eks_node_group.gpu[0].arn, null)
  description = "ARN do node group GPU."
}

output "karpenter_instance_profile" {
  value       = try(aws_iam_instance_profile.karpenter[0].name, null)
  description = "Instance profile usado pelo Karpenter."
}

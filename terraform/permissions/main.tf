resource "aws_iam_role" "eks_role" {
  name = "eks-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy_attachment" "eks_node_policy" {
  name       = "eks-node-policy"
  roles      = [aws_iam_role.eks_role.name]
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_policy_attachment" "eks_cni_policy" {
  name       = "eks-cni-policy"
  roles      = [aws_iam_role.eks_role.name]
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSCNIPolicy"
}

resource "aws_iam_policy_attachment" "eks_cluster_policy" {
  name       = "eks-cluster-policy"
  roles      = [aws_iam_role.eks_role.name]
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

output "eks_role_arn" {
  value = aws_iam_role.eks_role.arn
}
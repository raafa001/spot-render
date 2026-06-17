locals {
  tags = {
    Environment = var.environment
    Component   = "network"
  }
}

resource "aws_vpc" "this" {
  count                = var.create ? 1 : 0
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, {
    Name = "spot-render-${var.environment}"
  })
}

resource "aws_internet_gateway" "this" {
  count  = var.create ? 1 : 0
  vpc_id = aws_vpc.this[0].id

  tags = merge(local.tags, { Name = "spot-render-igw" })
}

resource "aws_subnet" "public" {
  count                   = var.create ? length(var.public_subnets) : 0
  vpc_id                  = aws_vpc.this[0].id
  cidr_block              = var.public_subnets[count.index]
  map_public_ip_on_launch = true
  availability_zone       = element(data.aws_availability_zones.available.names, count.index)

  tags = merge(local.tags, {
    Name = "spot-render-public-${count.index}"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  count             = var.create ? length(var.private_subnets) : 0
  vpc_id            = aws_vpc.this[0].id
  cidr_block        = var.private_subnets[count.index]
  availability_zone = element(data.aws_availability_zones.available.names, count.index)

  tags = merge(local.tags, {
    Name = "spot-render-private-${count.index}"
    Tier = "private"
  })
}

resource "aws_eip" "nat" {
  count = var.create ? length(var.private_subnets) : 0
  vpc   = true

  tags = merge(local.tags, { Name = "spot-render-nat-eip-${count.index}" })
}

resource "aws_nat_gateway" "this" {
  count         = var.create ? length(var.private_subnets) : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.tags, { Name = "spot-render-nat-${count.index}" })
}

resource "aws_route_table" "public" {
  count  = var.create ? 1 : 0
  vpc_id = aws_vpc.this[0].id

  tags = merge(local.tags, { Name = "spot-render-public" })
}

resource "aws_route" "public_internet" {
  count                  = var.create ? 1 : 0
  route_table_id         = aws_route_table.public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this[0].id
}

resource "aws_route_table_association" "public" {
  count          = var.create ? length(var.public_subnets) : 0
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_route_table" "private" {
  count  = var.create ? length(var.private_subnets) : 0
  vpc_id = aws_vpc.this[0].id

  tags = merge(local.tags, { Name = "spot-render-private-${count.index}" })
}

resource "aws_route" "private_internet" {
  count                  = var.create ? length(var.private_subnets) : 0
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[count.index].id
}

resource "aws_route_table_association" "private" {
  count          = var.create ? length(var.private_subnets) : 0
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_security_group" "database" {
  count  = var.create ? 1 : 0
  name   = "spot-render-db"
  vpc_id = aws_vpc.this[0].id

  description = "Banco de dados PostgreSQL"

  ingress {
    description = "PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "spot-render-db" })
}

resource "aws_cloudwatch_log_group" "flow_logs" {
  count             = var.create && var.enable_flow_logs ? 1 : 0
  name              = "/aws/vpc/spot-render-${var.environment}"
  retention_in_days = 7
  tags              = local.tags
}

resource "aws_flow_log" "this" {
  count                = var.create && var.enable_flow_logs ? 1 : 0
  log_destination      = aws_cloudwatch_log_group.flow_logs[0].arn
  log_destination_type = "cloud-watch-logs"
  traffic_type         = "ALL"
  vpc_id               = aws_vpc.this[0].id
  iam_role_arn         = aws_iam_role.flow_logs[0].arn
}

resource "aws_iam_role" "flow_logs" {
  count = var.create && var.enable_flow_logs ? 1 : 0
  name  = "spot-render-flow-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "flow_logs" {
  count = var.create && var.enable_flow_logs ? 1 : 0
  name  = "spot-render-flow-logs"
  role  = aws_iam_role.flow_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogGroups", "logs:DescribeLogStreams"]
      Resource = "${aws_cloudwatch_log_group.flow_logs[0].arn}:*"
    }]
  })
}

data "aws_availability_zones" "available" {
  state = "available"
}

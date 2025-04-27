provider "aws" {
  region = "us-east-1"
}

resource "aws_vpc" "spot-render-ntw" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "spot-render-subnet" {
  vpc_id     = aws_vpc.spot-render-ntw.id
  cidr_block = "10.0.1.0/24"
}

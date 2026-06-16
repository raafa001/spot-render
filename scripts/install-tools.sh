#!/bin/bash
set -euo pipefail

# install-tools.sh - Install required development tools on Ubuntu/Debian
# Usage: ./install-tools.sh

echo "=== install-tools.sh ==="

# Ensure running with sufficient privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "INFO: Not running as root. Some installations may require sudo."
    SUDO="sudo"
else
    SUDO=""
fi

# Update system
echo "Updating system packages..."
$SUDO apt update && $SUDO apt upgrade -y

# Install Git
echo "Installing Git..."
$SUDO apt install git -y
echo "Git version: $(git --version)"

# Install Terraform
echo "Installing Terraform..."
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | $SUDO tee /usr/share/keyrings/hashicorp-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | $SUDO tee /etc/apt/sources.list.d/hashicorp.list
$SUDO apt update && $SUDO apt install terraform -y
echo "Terraform version: $(terraform --version)"

# Install AWS CLI
echo "Installing AWS CLI..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
$SUDO ./aws/install
rm -rf awscliv2.zip aws/
echo "AWS CLI version: $(aws --version)"

# Install kubectl
echo "Installing kubectl..."
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
$SUDO mv kubectl /usr/local/bin/kubectl
echo "kubectl version: $(kubectl version --client --short)"

# Install Jenkins
echo "Installing Jenkins..."
$SUDO apt install openjdk-11-jdk -y
curl -fsSL https://pkg.jenkins.io/debian/jenkins.io.key | $SUDO tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
echo deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian binary/ | $SUDO tee /etc/apt/sources.list.d/jenkins.list > /dev/null
$SUDO apt update && $SUDO apt install jenkins -y
$SUDO systemctl start jenkins
$SUDO systemctl enable jenkins
echo "Jenkins installed. Access at http://localhost:8080"

echo "=== install-tools.sh completed ==="

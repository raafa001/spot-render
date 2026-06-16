#!/bin/bash
set -euo pipefail

# start-instances.sh - Start all EC2 instances with AutoOff=true tag that are stopped
# Usage: ./start-instances.sh

echo "=== start-instances.sh ==="

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
TAG_KEY="${TAG_KEY:-AutoOff}"
TAG_VALUE="${TAG_VALUE:-true}"

# Validate AWS CLI is installed
if ! command -v aws &>/dev/null; then
    echo "ERROR: AWS CLI is not installed. Please install it first."
    exit 1
fi

# Find stopped instances with matching tag
echo "Searching for stopped instances with tag $TAG_KEY=$TAG_VALUE in $AWS_REGION..."
INSTANCE_IDS=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" "Name=instance-state-name,Values=stopped" \
    --query "Reservations[*].Instances[*].InstanceId" \
    --output text)

# Verify and start instances
if [ -z "$INSTANCE_IDS" ]; then
    echo "No stopped instances found with tag $TAG_KEY=$TAG_VALUE."
else
    echo "Starting instances: $INSTANCE_IDS"
    aws ec2 start-instances --instance-ids $INSTANCE_IDS --region "$AWS_REGION"
    echo "Instances successfully started."
fi

echo "=== start-instances.sh completed ==="

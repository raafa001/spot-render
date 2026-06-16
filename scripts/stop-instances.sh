#!/bin/bash
set -euo pipefail

# stop-instances.sh - Stop all EC2 instances with AutoOff=true tag that are running
# Usage: ./stop-instances.sh

echo "=== stop-instances.sh ==="

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
TAG_KEY="${TAG_KEY:-AutoOff}"
TAG_VALUE="${TAG_VALUE:-true}"

# Validate AWS CLI is installed
if ! command -v aws &>/dev/null; then
    echo "ERROR: AWS CLI is not installed. Please install it first."
    exit 1
fi

# Find running instances with matching tag
echo "Searching for running instances with tag $TAG_KEY=$TAG_VALUE in $AWS_REGION..."
INSTANCE_IDS=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" "Name=instance-state-name,Values=running" \
    --query "Reservations[*].Instances[*].InstanceId" \
    --output text)

# Verify and stop instances
if [ -z "$INSTANCE_IDS" ]; then
    echo "No running instances found with tag $TAG_KEY=$TAG_VALUE."
else
    echo "Stopping instances: $INSTANCE_IDS"
    aws ec2 stop-instances --instance-ids $INSTANCE_IDS --region "$AWS_REGION"
    echo "Instances successfully stopped."
fi

echo "=== stop-instances.sh completed ==="

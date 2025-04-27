#!/bin/bash

# Variáveis
AWS_REGION="us-east-1"
TAG_KEY="AutoOff"
TAG_VALUE="true"

# Encontrar instâncias com a tag específica
INSTANCE_IDS=$(aws ec2 describe-instances \
  --region $AWS_REGION \
  --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" "Name=instance-state-name,Values=running" \
  --query "Reservations[*].Instances[*].InstanceId" \
  --output text)

# Verificar se há instâncias para desligar
if [ -z "$INSTANCE_IDS" ]; then
  echo "Nenhuma instância encontrada com a tag $TAG_KEY=$TAG_VALUE."
else
  echo "Desligando instâncias: $INSTANCE_IDS"
  aws ec2 stop-instances --instance-ids $INSTANCE_IDS --region $AWS_REGION
fi

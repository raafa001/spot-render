# Terraform Backend Bootstrap

> **PT-BR:** Este diretório cria o bucket S3 imutável utilizado como backend remoto do Terraform, com versionamento, Object Lock e política que exige MFA para exclusões. Rode este stack **antes** de executar `terraform init` em `infra/terraform`.
>
> **EN:** This folder provisions the immutable S3 bucket used as Terraform's remote backend, enforcing versioning, Object Lock, and MFA-aware delete policies. Run this stack **before** executing `terraform init` inside `infra/terraform`.

## Requisitos / Requirements

- AWS CLI configurado com acesso à conta alvo e permissão para criar S3, KMS e IAM policies.
- Dispositivo MFA associado ao usuário/role que executará o apply quando desejar habilitar deleções.

## Como usar / How to use

```bash
cd infra/terraform/bootstrap

# Opcional: definir profile/role
export AWS_PROFILE=spot-render-platform

terraform init
terraform apply \
  -var "bucket_name=spot-render-terraform-state" \
  -var "allow_delete_without_mfa_principals=['arn:aws:iam::123456789012:role/github-terraform']"
```

> **PT-BR:** Após o apply, habilite `MFA delete` para administradores executando:`aws s3api put-bucket-versioning --bucket <nome> --versioning-configuration Status=Enabled,MFADelete=Enabled --mfa "arn-of-mfa-device <token>"`. Este passo exige credenciais root + MFA e não pode ser automatizado.
>
> **EN:** After the apply, enable `MFA delete` for administrators with `aws s3api put-bucket-versioning --bucket <name> --versioning-configuration Status=Enabled,MFADelete=Enabled --mfa "arn-of-mfa-device <token>"`. AWS only allows this via root credentials + MFA, so it must be done manually.

## Saídas / Outputs

| Output | Descrição / Description |
| --- | --- |
| `bucket_name` | Nome do bucket remoto / Remote bucket name |
| `bucket_arn` | ARN completo do bucket / Bucket ARN |
| `kms_key_arn` | Chave usada para criptografia / Encryption key ARN |

## Política / Policy

> **PT-BR:** A política embutida nega deletar objetos do state sem MFA, exceto para os ARNs listados em `allow_delete_without_mfa_principals`. Utilize esta lista apenas para roles de automação que nunca executam `terraform state rm`.
>
> **EN:** The embedded bucket policy denies deleting state objects without MFA, except for the ARNs provided in `allow_delete_without_mfa_principals`. Use this escape hatch only for automation roles that never run destructive `terraform state rm` commands.

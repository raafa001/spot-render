# Terraform Hardening

> **PT-BR:** Este documento resume o endurecimento aplicado ao stack Terraform (`infra/terraform`) e como operar o backend S3 com Object Lock + MFA.
>
> **EN:** This document summarizes the hardening applied to the Terraform stack (`infra/terraform`) and how to operate the Object Lock + MFA S3 backend.

## Backend remoto / Remote backend

- **PT-BR:** Execute `infra/terraform/bootstrap` para criar o bucket `spot-render-terraform-state`, habilitar versionamento, Object Lock (30 dias) e a política que obriga MFA para deleções. Detalhes em [`infra/terraform/bootstrap/README.md`](../infra/terraform/bootstrap/README.md).
- **EN:** Run `infra/terraform/bootstrap` to create the `spot-render-terraform-state` bucket with versioning, 30-day Object Lock retention, and the MFA-aware delete policy. See [`infra/terraform/bootstrap/README.md`](../infra/terraform/bootstrap/README.md) for details.

## Segredos e variáveis / Secrets & repository variables

| Nome | Tipo | Descrição (PT-BR / EN) |
| --- | --- | --- |
| `AWS_TERRAFORM_ROLE_ARN` | Secret | **PT-BR:** Role assumida pelos jobs de `plan` e detecção de drift via OIDC. <br> **EN:** Role assumed by `plan` and drift jobs through OIDC. |
| `AWS_DEPLOY_ROLE_ARN` | Secret | **PT-BR:** Role privilegiada usada no `terraform-apply`. <br> **EN:** Privileged role consumed by `terraform-apply`. |
| `TF_STATE_BUCKET` | Repository variable (opcional) | **PT-BR:** Nome alternativo do bucket de state; default = `spot-render-terraform-state`. <br> **EN:** Optional override for the state bucket name; defaults to `spot-render-terraform-state`. |

## Pipeline CI/CD

> **PT-BR:** As workflows `terraform-plan.yml` e `terraform-apply.yml` agora executam a seguinte sequência obrigatória.
>
> **EN:** The `terraform-plan.yml` and `terraform-apply.yml` workflows now enforce the following sequence.

1. `terraform fmt -check -recursive`
2. `terraform validate`
3. `tflint --config infra/terraform/.tflint.hcl`
4. `checkov -d infra/terraform --framework terraform`
5. `terraform plan -out=tfplan.binary`
6. `conftest test tfplan.json --policy policy/terraform`

> **PT-BR:** Qualquer falha nessas etapas bloqueia o merge/deploy.
>
> **EN:** Any failure in these steps blocks merge/deploy.

## Detecção de drift / Drift detection

- **PT-BR:** `drift-detection.yml` executa diariamente (`cron 0 5 * * *`) e abre issues com label `drift` quando `terraform plan -detailed-exitcode` retorna `2`.
- **EN:** `drift-detection.yml` runs daily (`cron 0 5 * * *`) and opens `drift`-labelled issues when `terraform plan -detailed-exitcode` returns `2`.

## Policy-as-code (OPA)

- **PT-BR:** As políticas em `policy/terraform` são avaliadas pelo `conftest`. A primeira regra (`sg.rego`) impede que portas SSH (22) fiquem expostas para `0.0.0.0/0`.
- **EN:** Policies under `policy/terraform` are evaluated via `conftest`. The initial rule (`sg.rego`) blocks security groups exposing SSH (22) to `0.0.0.0/0`.

## Execução local / Local execution

```bash
cd infra/terraform
terraform fmt -recursive
terraform init -backend-config="bucket=$(terraform output -raw bucket_name --state=../bootstrap/terraform.tfstate)" \
  -backend-config="key=global/terraform.tfstate" \
  -backend-config="region=us-east-1"
terraform validate
tflint --config .tflint.hcl
checkov -d .
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
conftest test tfplan.json --policy ../../policy/terraform
```

> **PT-BR:** O comando `terraform output ...` supõe que você executou `bootstrap` e usa o mesmo diretório para armazenar o `terraform.tfstate` local daquele stack.
>
> **EN:** The `terraform output ...` command assumes you have already executed the `bootstrap` stack and are reusing its local `terraform.tfstate` file.

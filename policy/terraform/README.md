# Terraform Policy-as-Code

> **PT-BR:** As políticas `opa` neste diretório são executadas via `conftest` no pipeline Terraform para impedir configurações inseguras.
>
> **EN:** The `opa` policies in this folder are evaluated through `conftest` in the Terraform pipeline to block unsafe infrastructure changes.

## Políticas ativas / Active policies

| Arquivo | Descrição (PT-BR / EN) |
| --- | --- |
| `sg.rego` | **PT-BR:** Falha se algum `aws_security_group` expuser porta 22 (SSH) para `0.0.0.0/0`. <br> **EN:** Fails when any `aws_security_group` exposes SSH (port 22) to `0.0.0.0/0`. |

> **PT-BR:** Adicione novos arquivos `.rego` conforme surgirem requisitos de compliance (ex.: portas, tags obrigatórias, limites de custo).
>
> **EN:** Add additional `.rego` files as compliance requirements grow (e.g., port restrictions, mandatory tags, cost limits).

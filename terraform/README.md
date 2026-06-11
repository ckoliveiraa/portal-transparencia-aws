# Terraform — Infraestrutura como Código

Recria a stack do curso (S3, IAM, Secrets Manager, Lambda, EventBridge, Glue database).
Veja o passo a passo didático em [`modulos/09-terraform-iac`](../modulos/09-terraform-iac/README.md).

## Uso

```bash
cd terraform

# a chave da API vai por variável de ambiente (NUNCA commitada)
export TF_VAR_api_key="sua_chave_aqui"          # Linux/Mac
# $env:TF_VAR_api_key = "sua_chave_aqui"        # PowerShell

terraform init
terraform plan -out tf.plan -var "bucket_name=transparencia-datalake-SEUNOME"
terraform apply tf.plan
```

## Variáveis principais
| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `bucket_name` | Nome único do bucket | (obrigatório) |
| `region` | Região AWS | `us-east-1` |
| `secret_name` | Nome do segredo | `portal-transparencia/chave-api-dados` |
| `api_key` | Chave da API (via `TF_VAR_api_key`) | (sensível) |
| `schedule_expression` | Frequência da Lambda | `rate(15 minutes)` |
| `ano_mes` | Payload de coleta | `{ ano = 2024, mes = 1 }` |

## Observações
- A **Lambda Layer do `requests`** não está no Terraform — crie-a como no
  [Módulo 04](../modulos/04-lambda-ingestao/README.md) e descomente a linha `layers` em `main.tf`.
- O **Glue Job/Crawler** ficam como exercício (criados no console nos módulos 06/07);
  só o `database` é provisionado aqui.
- Para destruir tudo: `terraform destroy`.

## ⚠️ Nunca commite
`*.tfstate`, `*.tfvars` com segredos e a pasta `build/` já estão no `.gitignore`.

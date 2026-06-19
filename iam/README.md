# IAM — policies do projeto

Policies de **menor privilégio** usadas no curso. Antes de aplicar, troque os placeholders:

- `<projectname>` → sufixo do seu bucket (`transparencia-datalake-us-east-1-<projectname>`)
- `<conta>` → ID da sua conta AWS (12 dígitos)

| Arquivo | Role (nome no IAM) | Inline policy | Para que serve |
|---------|--------------------|---------------|----------------|
| [`lambda-trust-policy.json`](lambda-trust-policy.json) | `transparencia-ingestao-worker-role` + `transparencia-ingestao-dim-role` | — (trust) | Trust (Lambda assume a role) |
| [`worker-role-policy.json`](worker-role-policy.json) | `transparencia-ingestao-worker-role` | `worker-s3-secrets` | S3 Get/Put + ListBucket + ler o segredo |
| [`dim-role-policy.json`](dim-role-policy.json) | `transparencia-ingestao-dim-role` | `dim-s3-put` | só `s3:PutObject` em `raw/dim_municipios/*` |
| [`sfn-trust-policy.json`](sfn-trust-policy.json) | `transparencia-sfn-role` | — (trust) | Trust (`states.amazonaws.com`) |
| [`sfn-role-policy.json`](sfn-role-policy.json) | `transparencia-sfn-role` | `sfn-invoke-glue` | `lambda:InvokeFunction` no worker + `glue:StartJobRun/GetJobRun/BatchStopJobRun` |
| [`glue-trust-policy.json`](glue-trust-policy.json) | `transparencia-glue-role` | — (trust) | Trust (`glue.amazonaws.com`) |
| [`glue-role-policy.json`](glue-role-policy.json) | `transparencia-glue-role` | `glue-s3-rw` | ler `raw`, escrever/apagar `curated*`, ListBucket |

Managed policies que completam cada role:
- **Lambdas** (worker/dim): `AWSLambdaBasicExecutionRole` (logs no CloudWatch).
- **Glue**: `AWSGlueServiceRole` (operação do job) — além da inline acima.

Passo a passo de criação (UI e contexto): Lambda no [Módulo 04](../modulos/04-lambda-ingestao/README.md),
Glue no [Módulo 05](../modulos/05-glue-transformacao/README.md), Step Functions no
[Módulo 06](../modulos/06-step-functions-orquestracao/README.md).

> ⚠️ Gotchas (todos reais do projeto):
> - `s3:ListBucket` é no ARN do **bucket** (sem `/*`) — sem isso, `GetObject` em objeto
>   inexistente vira `AccessDenied` e quebra o `ler_checkpoint`.
> - A policy do Glue cobre **`curated*`** (sem `/`) porque o committer do Spark cria um marcador
>   `curated_$folder$` na **raiz** do bucket; com `curated/*` daria `AccessDenied`.
> - `lambda:InvokeFunction` fica **só** na role do Step Functions, não na da Lambda.

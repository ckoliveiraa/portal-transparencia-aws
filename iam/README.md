# IAM — policies do projeto

Policies de **menor privilégio** usadas no curso. Antes de aplicar, troque os placeholders:

- `<projectname>` → sufixo do seu bucket (`transparencia-datalake-us-east-1-<projectname>`)
- `<conta>` → ID da sua conta AWS (12 dígitos)

| Arquivo | Role | Para que serve |
|---------|------|----------------|
| [`lambda-trust-policy.json`](lambda-trust-policy.json) | worker + dim | Trust (Lambda assume a role) |
| [`worker-role-policy.json`](worker-role-policy.json) | worker | S3 Get/Put + ListBucket + ler o segredo |
| [`dim-role-policy.json`](dim-role-policy.json) | dim | só `s3:PutObject` em `raw/dim_municipios/*` |
| [`sfn-trust-policy.json`](sfn-trust-policy.json) | Step Functions | Trust (`states.amazonaws.com`) |
| [`sfn-role-policy.json`](sfn-role-policy.json) | Step Functions | `lambda:InvokeFunction` no worker + `glue:StartJobRun/GetJobRun/BatchStopJobRun` |
| [`glue-trust-policy.json`](glue-trust-policy.json) | Glue | Trust (`glue.amazonaws.com`) |
| [`glue-role-policy.json`](glue-role-policy.json) | Glue | ler `raw`, escrever/apagar `curated*`, ListBucket |

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

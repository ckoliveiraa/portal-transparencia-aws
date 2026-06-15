# IAM — policies do projeto

Policies de **menor privilégio** usadas no curso. Antes de aplicar, troque os placeholders:

- `<projectname>` → sufixo do seu bucket (`transparencia-datalake-us-east-1-<projectname>`)
- `<conta>` → ID da sua conta AWS (12 dígitos)

| Arquivo | Para que serve |
|---------|----------------|
| [`lambda-trust-policy.json`](lambda-trust-policy.json) | Trust policy (Lambda assume a role) — vale para as duas Lambdas |
| [`worker-role-policy.json`](worker-role-policy.json) | Inline da role do **worker**: S3 Get/Put + ListBucket + ler o segredo |
| [`dim-role-policy.json`](dim-role-policy.json) | Inline da role do **dim**: só `s3:PutObject` em `raw/dim_municipios/*` |

Cada role também recebe a managed `AWSLambdaBasicExecutionRole` (logs no CloudWatch).
Passo a passo de criação (UI e contexto) no [Módulo 04](../modulos/04-lambda-ingestao/README.md).

> ⚠️ `s3:ListBucket` é no ARN do **bucket** (sem `/*`) — sem isso, `GetObject` em objeto
> inexistente vira `AccessDenied` e quebra o `ler_checkpoint`.
> `lambda:InvokeFunction` **não** entra aqui — fica na role do Step Functions (Módulo 06).

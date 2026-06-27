# Módulo 09 — Limpeza (teardown)

## 🎯 Objetivo
**Desmontar tudo** que você criou no curso para não gerar cobranças.

## 🧠 Conceitos
- **Teardown**: remover recursos é parte do ciclo; recursos esquecidos = conta surpresa.
- **O que cobra parado vs. por uso**: alguns serviços só cobram quando rodam; outros cobram só por existir (ver tabela abaixo).
- **Ordem importa**: derrube primeiro o que **fica rodando/sondando**, depois o resto.

## ✅ Pré-requisitos
- Ter rodado os módulos anteriores.

## 🧹 Limpeza

### O que realmente gera cobrança? (priorize estes)
| Recurso | Cobra mesmo parado? | Por quê |
|---|---|---|
| 🔴 **EventBridge Scheduler** (desafio) | **Sim, todo dia** | Sonda a API sozinho para sempre — **apague PRIMEIRO** |
| 🔴 **S3 bucket** (dados) | **Sim** | Você paga pelo armazenamento enquanto os objetos existirem |
| 🟡 **Secrets Manager** | Sim (~US$0,40/mês por segredo) | Cobrança fixa por segredo guardado |
| 🟡 **CloudWatch Logs** | Sim, se houver retenção infinita | Armazenamento de logs antigos acumula |
| 🟢 Lambda / Glue job / State machine | **Não** (só por uso) | Sem invocação = sem custo, mas remova por higiene |
| 🟢 Roles/policies IAM | **Não** | Não custam nada, mas remova para não deixar lixo |

> ⚠️ A ordem importa: derrube primeiro o que **fica rodando/sondando** (Scheduler), depois o resto.

### B1 — Se você fez o Desafio final (Módulo 08), remova **primeiro** o que ele criou
> Estes são os recursos que **não existem** para quem não fez o desafio. O Scheduler é o mais
> urgente: enquanto existir, ele invoca a Lambda detector todos os dias **para sempre**.

```bash
# 1) Scheduler do detector (PARA o polling diário — faça isto antes de tudo)
aws scheduler delete-schedule --name transparencia-detector-diario

# 2) Lambda detector
aws lambda delete-function --function-name transparencia-detector-mes

# 3) IAM do desafio — role/policy da Lambda detector + role do Scheduler
#    (ajuste os nomes para os que você criou). Primeiro solte as policies, depois apague as roles.
aws iam delete-role-policy --role-name transparencia-detector-role --policy-name transparencia-detector-policy
aws iam delete-role --role-name transparencia-detector-role
aws iam delete-role --role-name transparencia-detector-scheduler-role
# Se você usou policies gerenciadas (managed) em vez de inline:
#   aws iam detach-role-policy --role-name <role> --policy-arn <arn>
#   aws iam delete-policy --policy-arn <arn>
```

### B2 — Recursos do pipeline principal (todos os alunos)
```bash
# 4) State machine (não fica nada rodando — ela termina sozinha)
aws stepfunctions delete-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:<account>:stateMachine:transparencia-ingestao

# 5) Lambda worker + Layer
aws lambda delete-function --function-name SUA-FUNCAO

# 6) Glue: job e database (não há crawler — Option A)
aws glue delete-job --job-name transparencia-glue-bolsa-familia
aws glue delete-database --name transparencia

# 7) Secret (PARA a cobrança fixa mensal do segredo)
aws secretsmanager delete-secret --secret-id portal-transparencia/chave-api-dados \
  --force-delete-without-recovery

# 8) Esvaziar e remover o bucket (CUIDADO: apaga os dados — é o que mais pesa na fatura)
aws s3 rm s3://transparencia-datalake-us-east-1-<projectname> --recursive
aws s3 rb s3://transparencia-datalake-us-east-1-<projectname>

# 9) IAM do pipeline — roles do worker, do Glue e da state machine (Módulos 04/06/07)
#    Solte as policies inline e apague as roles (ajuste os nomes aos seus).
aws iam delete-role --role-name transparencia-lambda-role
aws iam delete-role --role-name transparencia-glue-role
aws iam delete-role --role-name transparencia-sfn-role
```

### B3 — Faxina final
- **CloudWatch Logs**: apague os *log groups* `/aws/lambda/*` e `/aws-glue/*` do projeto (ou
  defina retenção curta) para não acumular armazenamento.
- **Alarmes/SNS**: remova alarmes e tópicos que tenha criado — **mas mantenha o alarme de billing!**

## 🔍 Validação
- `aws s3 ls | grep transparencia` não retorna nada.
- `aws lambda list-functions` não lista nem o worker **nem o detector** (se fez o desafio).
- `aws scheduler list-schedules` não lista `transparencia-detector-diario` (o que mais importa: o polling parou).
- `aws secretsmanager list-secrets` não lista o segredo da chave.
- `aws iam list-roles | grep transparencia` não retorna nada (roles do pipeline e do desafio removidas).
- Cost Explorer no dia seguinte mostra gasto tendendo a zero.

## 💲 Custos / Free Tier
- CloudWatch Logs: 5 GB de ingestão grátis. Nossos logs → **zero**.
- **A limpeza é o que garante custo final ≈ centavos.**

## 🎓 Fim da trilha
Você construiu um pipeline de dados serverless completo: **API → Lambda → S3 → Glue → Athena**,
com boas práticas de segurança e custo — e, se encarou o
[Desafio final (Módulo 08)](../08-desafio-final-auto-check/README.md), ainda o deixou **autônomo**.

Próximos passos (fase 2): QuickSight (BI), CI/CD e drill-down por beneficiário.

⬅️ Voltar ao [índice do curso](../../README.md)

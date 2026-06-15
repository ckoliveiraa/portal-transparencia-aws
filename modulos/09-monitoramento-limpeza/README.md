# Módulo 09 — Monitoramento e limpeza

## 🎯 Objetivo
Observar o pipeline (logs/métricas) e **desmontar tudo** para não gerar cobranças.

## 🧠 Conceitos
- **CloudWatch Logs**: cada Lambda/Glue job escreve logs em um *log group*.
- **CloudWatch Metrics/Alarms**: métricas (invocações, erros, duração) e alarmes.
- **Observabilidade**: saber se o pipeline rodou, falhou ou está caro — antes do cliente (ou da fatura) avisar.
- **Teardown**: remover recursos é parte do ciclo; recursos esquecidos = conta surpresa.

## ✅ Pré-requisitos
- Ter rodado os módulos anteriores.

## 🪜 Parte A — Monitoramento
1. **Logs da Lambda**: CloudWatch → *Log groups* → `/aws/lambda/SUA-FUNCAO`. Veja o JSON de progresso de cada lote.
2. **Métricas**: CloudWatch → *Metrics* → `Lambda` → `Errors`, `Duration`, `Invocations`.
3. **Alarme de erro** (opcional): crie um alarme em `Errors > 0` que te notifica por e-mail.
4. **Billing**: confira *Billing* → *Cost Explorer* para ver o gasto por serviço.

## 🧹 Parte B — Limpeza (na ordem)
> Remova os recursos criados no console, na ordem abaixo:

```bash
# 1) Remover a state machine (não fica nada rodando — ela já termina sozinha)
aws stepfunctions delete-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:<account>:stateMachine:transparencia-ingestao

# 2) Lambda + Layer
aws lambda delete-function --function-name SUA-FUNCAO

# 3) Glue: job, crawlers e database
aws glue delete-database --name transparencia

# 4) Secret
aws secretsmanager delete-secret --secret-id portal-transparencia/chave-api-dados \
  --force-delete-without-recovery

# 5) Esvaziar e remover o bucket (CUIDADO: apaga os dados)
aws s3 rm s3://transparencia-datalake-us-east-1-<projectname> --recursive
aws s3 rb s3://transparencia-datalake-us-east-1-<projectname>
```
5. **Conferir alarmes/SNS** e remover o que não usar mais (mantenha o alarme de billing!).

## 🔍 Validação
- `aws s3 ls | grep transparencia` não retorna nada.
- `aws lambda list-functions` não lista a função.
- Cost Explorer no dia seguinte mostra gasto tendendo a zero.

## 💲 Custos / Free Tier
- CloudWatch Logs: 5 GB de ingestão grátis. Nossos logs → **zero**.
- **A limpeza é o que garante custo final ≈ centavos.**

## 🎓 Fim da trilha
Você construiu um pipeline de dados serverless completo: **API → Lambda → S3 → Glue → Athena**,
com boas práticas de segurança e custo.

➡️ **Quer fechar com chave de ouro?** Encare o
[Desafio final — auto-check de novos meses](../10-desafio-final-auto-check/README.md): deixe o
pipeline **autônomo**, detectando e processando cada mês novo sozinho.

Outros próximos passos (fase 2): QuickSight (BI), CI/CD e drill-down por beneficiário.

⬅️ Voltar ao [índice do curso](../../README.md)

# Arquitetura

Pipeline de dados serverless na AWS, no padrão **data lake em camadas (medallion)**.
Cada serviço é introduzido em um módulo do curso.

## Visão geral

```
IBGE API (1 chamada) ─────> [Lambda dim] ──────> S3 RAW/dim_municipios (5.571)
                                                       │
API Portal Transparência ──> [Lambda worker em LOTES] ──> S3 RAW (bronze, JSON)
 (1 req/município, 30/min)        │   ▲                    raw/ano=/mes=/uf=/cod.json
                           Secrets Manager │                    │
                                 │   checkpoint (S3)       [Glue Job PySpark]
      EventBridge (a cada ~15min)┘   retoma até fechar     limpa+achata+Parquet
                                      o mês (~14 lotes)    S3 CURATED (silver, ano/mes)
                                                                │
                                                   [Glue Crawler → Data Catalog]
                                                                │
                                                     Athena (SQL: top 15 +/-)
      Tudo: IAM (least privilege) · CloudWatch (logs) · Terraform (módulo final)
```

## Camadas do data lake

| Camada | Prefixo S3 | Formato | Conteúdo |
|--------|-----------|---------|----------|
| **RAW (bronze)** | `raw/bolsa_familia/ano=/mes=/uf=/` | JSON | Resposta crua da API, 1 arquivo por município/mês |
| **RAW (dim)** | `raw/dim_municipios/` | CSV | Dimensão de municípios (IBGE), 5.571 linhas |
| **CURATED (silver)** | `curated/bolsa_familia/ano=/mes=/` | Parquet | Dados limpos, achatados, tipados e particionados |
| **Checkpoints** | `_checkpoints/AAAAMM.json` | JSON | Controle de progresso da ingestão em lotes |

Por que camadas? Separar **dado bruto imutável** (auditável, reprocessável) do **dado
tratado** (otimizado para consulta) é um princípio central de engenharia de dados.

## Glossário de serviços AWS

| Serviço | Papel no projeto | Módulo |
|---------|------------------|--------|
| **IAM** | Identidade e permissões (usuário, roles, least privilege) | 00 |
| **S3** | Armazenamento do data lake (raw + curated) | 02 |
| **Secrets Manager** | Guarda a `chave-api-dados` com segurança | 03 |
| **Lambda** | Computação serverless: ingestão da dim e dos fatos (worker em lotes) | 04 |
| **EventBridge** | Agendador: re-invoca a Lambda até fechar o mês | 05 |
| **Glue (Job)** | ETL Spark: transforma JSON bruto em Parquet | 06 |
| **Glue (Crawler/Catalog)** | Descobre o schema e cria as tabelas (metastore) | 07 |
| **Athena** | Consulta SQL serverless sobre o S3 | 08 |
| **CloudWatch** | Logs e métricas das Lambdas e jobs | 04, 10 |
| **Terraform** | Infraestrutura como código (recria tudo) | 09 |

## Por que a ingestão é em lotes (e não paralela)

A API exige **1 chamada por município** (`codigoIbge` obrigatório) → 5.571 chamadas/mês.
O **rate limit de 30 req/min** é o gargalo, e **paralelizar não ajuda** (geraria `429`).
Logo, a coleta é **sequencial** (~1 req/2s ≈ 3h/mês) e distribuída em vários lotes,
porque a Lambda tem teto de **15 minutos**:

- cada invocação processa ~400 municípios e salva um **checkpoint** (offset) no S3;
- a próxima invocação **retoma** de onde parou;
- é **idempotente**: se o JSON do município já existe no S3, pula (re-execução segura);
- ao atingir 5.571, grava um marcador `_SUCCESS` e para.

Conceitos de engenharia de dados exercitados: **idempotência, checkpoint/retomada,
rate limiting, retry com backoff, time budget, particionamento**.

## Decisões e trade-offs

- **Tudo via API** (em vez do download em massa CSV): escolha didática — ensina auth,
  rate limit e fan-out. Custo: ~3h/mês de coleta vs. 1 arquivo instantâneo.
- **Lambda em lotes** (em vez de Fargate/Glue Python Shell): foca o aprendizado em
  Lambda, idempotência e checkpoint. Para um job de 3h "de verdade", Fargate seria o
  encaixe mais natural — fica como nota de evolução.
- **Console primeiro, Terraform depois**: o aluno vê cada serviço na mão antes de
  automatizar com IaC.

## Fora de escopo (fase 2)

Step Functions (orquestração dos lotes), QuickSight (BI/dashboard), CI/CD (GitHub Actions)
e o **drill-down por beneficiário** (arquivo de Pagamentos, ~20M linhas/mês).

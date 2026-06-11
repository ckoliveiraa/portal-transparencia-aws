# Módulo 06 — Glue (transformação com PySpark)

## 🎯 Objetivo
Transformar os JSONs brutos (RAW) em **Parquet** limpo e particionado (CURATED), pronto para consulta.

## 🧠 Conceitos
- **AWS Glue**: serviço de ETL serverless baseado em **Apache Spark**.
- **PySpark**: API Python do Spark para processar dados em escala.
- **Achatar (flatten)**: transformar JSON aninhado (`municipio.uf.sigla`) em colunas planas (`uf_sigla`).
- **Parquet**: formato **colunar** e comprimido — muito mais rápido/barato no Athena que JSON.
- **Partição**: gravar por `ano/mes` permite o Athena ler só o necessário.

## ✅ Pré-requisitos
- Dados RAW no S3 (Módulos 02/04).

## 🧩 O código (já pronto)
`glue/job_bolsa_familia.py`:
- lê `raw/bolsa_familia/.../*.json`;
- `explode()` do array → 1 linha por registro;
- seleciona/renomeia campos aninhados em colunas planas;
- deriva `ano`/`mes` da `dataReferencia`;
- grava Parquet particionado em `curated/bolsa_familia/`.

## 🪜 Passo a passo (console)
1. **Subir o script** para o S3 (ex.: `s3://.../scripts/job_bolsa_familia.py`).
2. Glue → *ETL jobs* → *Script editor* → cole/aponte o script. Tipo: **Spark**.
3. **IAM Role do Glue** com acesso de leitura/escrita ao bucket.
4. **Job parameters**: adicione `--BUCKET = transparencia-datalake-SEUNOME`.
5. **Workers**: o mínimo (ex.: 2 DPUs / G.1X) — nosso volume é pequeno.
6. *Run job* e acompanhe.

## 🔍 Validação
```bash
aws s3 ls s3://.../curated/bolsa_familia/ --recursive | head
```
Devem aparecer arquivos `.parquet` sob `ano=2024/mes=1/`. O log do job imprime a contagem de linhas.

## 🏋️ Exercícios
1. Adicione uma coluna `valor_medio = valor / qtd_beneficiados`.
2. Rode o job de novo e confirme que a partição é **sobrescrita** (idempotente), não duplicada.

## 💲 Custos / Free Tier
- ⚠️ **Glue NÃO tem Free Tier.** ~**US$ 0,44/DPU-hora**, mínimo 2 DPUs, cobrança por segundo (mín. 1 min).
- Um job pequeno custa **centavos**. Para economizar: poucos DPUs, dados pequenos, rode sob demanda (não em loop). Lembre de não deixar *development endpoints* ligados.

## 🧹 Limpeza
- O job em si não cobra parado; só ao rodar. Remova-o no Módulo 10.

➡️ Próximo: [Módulo 07 — Glue Crawler / Catalog](../07-glue-catalog-crawler/README.md)

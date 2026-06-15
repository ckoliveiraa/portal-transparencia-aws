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
1. **Subir o script** para o S3: `s3://transparencia-datalake-us-east-1-training/scripts/job_bolsa_familia.py`.
2. Glue → *ETL jobs* → *Script editor* → cole/aponte o script. Tipo: **Spark**, Python.
   Nome do job: `transparencia-glue-bolsa-familia`. **Glue version 4.0**.
3. **IAM Role do Glue** (`transparencia-glue-role`): managed `AWSGlueServiceRole` + inline S3
   (ler `raw/`, escrever/apagar `curated*`, `ListBucket`).
4. **Job parameters**: adicione `--BUCKET = transparencia-datalake-us-east-1-training`.
5. **Workers**: **G.1X**, **2** (volume pequeno).
6. *Run job* e acompanhe em **Runs**.

> ⚠️ **Gotcha real — `curated_$folder$` (403):** o committer do Spark cria um marcador de pasta
> `curated_$folder$` **na raiz do bucket**, fora de `curated/`. Se a policy liberar só `curated/*`,
> dá **AccessDenied**. Cura: liberar `curated*` (sem a barra) no `s3:PutObject`. O marcador é um
> objeto de 0 byte inofensivo — Athena/Glue o ignoram.

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
- O job em si não cobra parado; só ao rodar. Remova-o no Módulo 09.

➡️ Próximo: [Módulo 07 — Glue Crawler / Catalog](../07-glue-catalog-crawler/README.md)

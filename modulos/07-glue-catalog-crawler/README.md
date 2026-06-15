# Módulo 07 — Glue Crawler e Data Catalog

## 🎯 Objetivo
Catalogar os dados do S3 como **tabelas** para o Athena consultar via SQL.

> 🔀 **Duas formas de catalogar — escolha uma:**
> - **Crawler (automático)** — este módulo: um robô infere o schema e cria as tabelas.
> - **DDL manual (na mão)** — o que fizemos na prática, direto no editor do Athena
>   (`CREATE EXTERNAL TABLE` + `MSCK REPAIR TABLE`), ótimo para o aluno **ver o schema**.
>   Está no [Módulo 08](../08-athena-analise/README.md). Faça **só uma** das duas.

## 🧠 Conceitos
- **Glue Data Catalog**: um "metastore" — guarda o **schema** (colunas, tipos, partições) das tabelas, mas **não** os dados (que ficam no S3).
- **Crawler**: robô que varre um caminho no S3, infere o schema e cria/atualiza a tabela no Catalog.
- **Database (Glue)**: agrupador lógico de tabelas (ex.: `transparencia`).
- **Partições**: o crawler reconhece `ano=/mes=` como colunas de partição automaticamente.

## ✅ Pré-requisitos
- CURATED em Parquet (Módulo 06) e a dim CSV no S3 (Módulo 02).

## 🪜 Passo a passo (console)
1. Glue → *Databases* → *Add database*: `transparencia`.
2. **Crawler dos fatos** (`transparencia-bolsa-familia-crawler`): Glue → *Crawlers* → *Create crawler*.
   - Source: `s3://.../curated/bolsa_familia/`.
   - IAM role com acesso ao bucket (a mesma `transparencia-glue-role` serve).
   - Target database: `transparencia`; prefixo de tabela: (vazio).
   - *Run* → cria a tabela `bolsa_familia` com partições `ano`, `mes`.
   > 🔗 É **este** crawler que a state machine do [Módulo 05](../05-step-functions-orquestracao/README.md)
   > roda automaticamente após o Glue. Para ele só **adicionar partições** sem mexer numa tabela já
   > criada na mão (DDL do Módulo 08), use *Schema change policy* = **Log** e *partições* herdando
   > da tabela.
3. **Crawler da dim**: repita apontando para `s3://.../raw/dim_municipios/` → tabela `dim_municipios`.
   > Para CSV, confirme que o crawler detectou o cabeçalho (senão ajuste o classifier).

## 🔍 Validação
```bash
aws glue get-tables --database-name transparencia --query "TableList[].Name"
```
Deve listar `bolsa_familia` e `dim_municipios`. No console do Athena elas aparecem no database `transparencia`.

## 💲 Custos / Free Tier
- Catalog: **1 milhão de objetos armazenados grátis** + 1M de requisições/mês. Crawler: ~US$ 0,44/DPU-h enquanto roda (segundos). → **centavos ou zero**.

## 🧹 Limpeza
- Remova crawlers, tabelas e o database no Módulo 09 (`aws glue delete-database --name transparencia`).

➡️ Próximo: [Módulo 08 — Athena](../08-athena-analise/README.md)

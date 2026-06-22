# Módulo 05 — Glue (transformação com PySpark)

## 🎯 Objetivo
Transformar os JSONs brutos (RAW) em **Parquet** limpo e particionado (CURATED), pronto para consulta.

## 🧠 Conceitos
- **AWS Glue**: serviço de ETL serverless baseado em **Apache Spark**.
- **PySpark**: API Python do Spark para processar dados em escala.
- **Achatar (flatten)**: transformar JSON aninhado (`municipio.uf.sigla`) em colunas planas (`uf_sigla`).
- **Parquet**: formato **colunar** e comprimido — muito mais rápido/barato no Athena que JSON.
- **Partição**: gravar por `ano/mes` permite o Athena ler só o necessário.
- **Job cataloga sozinho**: ao final, o próprio job roda `ALTER TABLE ... ADD PARTITION` no Glue
  Data Catalog (precisa do parâmetro `--enable-glue-datacatalog`). Assim o Athena já enxerga as
  partições novas — **sem crawler e sem `MSCK REPAIR` manual**.

## ✅ Pré-requisitos
- Dados RAW no S3: rode o **worker** (Módulo 04) algumas vezes para ter JSONs em
  `raw/bolsa_familia/`. Pode ser um mês **parcial** — basta para aprender o ETL; a coleta do mês
  **completo** é automatizada depois pelo **Step Functions** (Módulo 07).
- A tabela `transparencia.bolsa_familia` **ainda não precisa existir**: ela é criada via DDL no
  **Módulo 06** (Athena). Enquanto não existir, o job grava o Parquet normalmente e só **avisa** no
  log que não catalogou — passa a catalogar (`ADD PARTITION`) assim que a tabela existir.

## 🧩 O código (já pronto)
`glue/job_bolsa_familia.py`:
- lê `raw/bolsa_familia/.../*.json`;
- `explode()` do array → 1 linha por registro;
- seleciona/renomeia campos aninhados em colunas planas;
- deriva `ano`/`mes` da `dataReferencia`;
- grava Parquet particionado em `curated/bolsa_familia/` (idempotente, *dynamic overwrite*);
- **registra as partições escritas no Data Catalog** (`ADD IF NOT EXISTS PARTITION`).

<details>
<summary>📄 <code>glue/job_bolsa_familia.py</code> — código completo (clique para copiar)</summary>

```python
"""
Glue Job (PySpark) — Módulo 05.

Lê os JSONs brutos do Bolsa Família na camada RAW, achata a estrutura
aninhada, normaliza tipos e grava em Parquet na camada CURATED,
particionado por ano/mes. Ao final, o PRÓPRIO job registra as partições
novas no Glue Data Catalog (ALTER TABLE ... ADD PARTITION) — sem crawler
e sem MSCK manual. Assim o Athena (Módulo 06) já enxerga os dados.

RAW     : s3://BUCKET/raw/bolsa_familia/ano=*/mes=*/uf=*/municipio=*.json
CURATED : s3://BUCKET/curated/bolsa_familia/ano=*/mes=*/  (Parquet)

Parâmetros do Job (--KEY value):
  --BUCKET   nome do bucket S3

Requer o Job parameter --enable-glue-datacatalog (faz o Spark usar o Glue
Data Catalog como metastore, habilitando o ALTER TABLE ADD PARTITION).
A tabela transparencia.bolsa_familia precisa existir (criada via DDL,
Módulo 06) — o job só ADICIONA partições, herdando o schema da tabela.

Observação didática: cada arquivo RAW contém um array com 1 objeto
(o registro daquele município/mês). Usamos explode() para transformar
o array em linhas e depois selecionamos os campos aninhados.
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET"])
bucket = args["BUCKET"]

DATABASE = "transparencia"
TABLE = "bolsa_familia"

sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
job = Job(glue)
job.init(args["JOB_NAME"], args)

raw_path = f"s3://{bucket}/raw/bolsa_familia/"
curated_path = f"s3://{bucket}/curated/bolsa_familia/"

# 1) Lê todos os JSONs da camada RAW.
#    recursiveFileLookup ignora a estrutura de pastas ano=/mes=/uf= ao ler,
#    mas os campos ano/mes/uf também vêm do conteúdo, então não dependemos disso.
df = (
    spark.read
    .option("multiLine", "true")
    .json(f"{raw_path}*/*/*/*.json")
)

# 2) Cada arquivo é um array -> explode para 1 linha por registro.
#    (Spark já infere o array de objetos; explode normaliza.)
if "municipio" not in df.columns:
    # quando o JSON é um array no topo, o Spark lê como coluna implícita
    df = df.select(F.explode(F.col("value")).alias("r")).select("r.*")

# 3) Achata os campos aninhados em colunas planas.
flat = df.select(
    F.col("id").cast("long").alias("id"),
    F.to_date("dataReferencia").alias("data_referencia"),
    F.col("municipio.codigoIBGE").alias("codigo_ibge"),
    F.col("municipio.nomeIBGE").alias("municipio"),
    F.col("municipio.uf.sigla").alias("uf_sigla"),
    F.col("municipio.nomeRegiao").alias("regiao_nome"),
    F.col("tipo.descricao").alias("programa"),
    F.col("valor").cast("double").alias("valor"),
    F.col("quantidadeBeneficiados").cast("long").alias("qtd_beneficiados"),
)

# 4) Deriva ano/mes (colunas de partição) a partir da data de referência.
final = (
    flat
    .withColumn("ano", F.year("data_referencia"))
    .withColumn("mes", F.month("data_referencia"))
    .filter(F.col("codigo_ibge").isNotNull())
)

# 5) Grava Parquet particionado (idempotente p/ as partições reprocessadas).
(
    final.write
    .mode("overwrite")
    .partitionBy("ano", "mes")
    .option("partitionOverwriteMode", "dynamic")
    .parquet(curated_path)
)

print(f"OK: {final.count()} linhas gravadas em {curated_path}")

# 6) CATALOGA: registra as partições escritas no Data Catalog (Option A).
#    ADD IF NOT EXISTS é idempotente; herda o schema da tabela (criada no DDL).
#    Requer --enable-glue-datacatalog. Se a tabela ainda não existe, só avisa.
particoes = [(r["ano"], r["mes"]) for r in final.select("ano", "mes").distinct().collect()]
try:
    for ano_p, mes_p in particoes:
        spark.sql(
            f"ALTER TABLE {DATABASE}.{TABLE} "
            f"ADD IF NOT EXISTS PARTITION (ano={ano_p}, mes={mes_p})"
        )
    print(f"Catalogo atualizado: {len(particoes)} particao(oes) -> {particoes}")
except Exception as e:  # noqa: BLE001 — não falhar o job por causa do catálogo
    print(f"AVISO: nao registrei particoes (a tabela {DATABASE}.{TABLE} existe? "
          f"crie via DDL no Modulo 06): {e}")

job.commit()
```

</details>

## 🔐 IAM — policies (prontas para copiar)
A role `transparencia-glue-role` usa trust em `glue.amazonaws.com`, a managed
`AWSGlueServiceRole` **e** a inline S3 abaixo (arquivos em [`iam/`](../../iam/); troque `<projectname>`).

<details>
<summary>📄 <code>iam/glue-trust-policy.json</code> — trust (quem assume a role)</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "glue.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

</details>

<details>
<summary>📄 <code>iam/glue-role-policy.json</code> — inline (S3: ler raw, escrever curated)</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LerRaw",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>/*"
    },
    {
      "Sid": "EscreverCurated",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>/curated*"
    },
    {
      "Sid": "ListarBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>"
    }
  ]
}
```

> ⚠️ `curated*` (sem `/`) é proposital — ver o gotcha do `curated_$folder$` abaixo.

</details>

## 🪜 Passo a passo (console)
1. **Subir o script** para o S3: `s3://transparencia-datalake-us-east-1-<projectname>/scripts/job_bolsa_familia.py`.
2. Glue → *ETL jobs* → *Script editor* → cole/aponte o script. Tipo: **Spark**, Python.
   Nome do job: `transparencia-glue-bolsa-familia`. **Glue version 5.1**.
3. **IAM Role do Glue** (`transparencia-glue-role`): managed `AWSGlueServiceRole` + inline S3
   (ler `raw/`, escrever/apagar `curated*`, `ListBucket`).
4. **Job parameters**: adicione
   - `--BUCKET = transparencia-datalake-us-east-1-<projectname>`;
   - `--enable-glue-datacatalog` (sem valor) — habilita o `ADD PARTITION` no catálogo.
5. **Workers**: **G.1X**, **2** (volume pequeno).
6. *Run job* e acompanhe em **Runs**.
   - 👀 No log: `OK: N linhas gravadas` e `Catalogo atualizado: 1 particao(oes)`.

> ⚠️ **Gotcha real — `curated_$folder$` (403):** o committer do Spark cria um marcador de pasta
> `curated_$folder$` **na raiz do bucket**, fora de `curated/`. Se a policy liberar só `curated/*`,
> dá **AccessDenied**. Cura: liberar `curated*` (sem a barra) no `s3:PutObject`. O marcador é um
> objeto de 0 byte inofensivo — Athena/Glue o ignoram.

## 🔍 Validação
```bash
aws s3 ls s3://.../curated/bolsa_familia/ --recursive | head
```
Devem aparecer arquivos `.parquet` sob `ano=2026/mes=4/`. O log do job imprime a contagem de linhas.

## 💲 Custos / Free Tier
- ⚠️ **Glue NÃO tem Free Tier.** ~**US$ 0,44/DPU-hora**, mínimo 2 DPUs, cobrança por segundo (mín. 1 min).
- Um job pequeno custa **centavos**. Para economizar: poucos DPUs, dados pequenos, rode sob demanda (não em loop). Lembre de não deixar *development endpoints* ligados.

## 🧹 Limpeza
- O job em si não cobra parado; só ao rodar. Remova-o no Módulo 09.

➡️ Próximo: [Módulo 06 — Athena + Data Catalog](../06-athena-analise/README.md)

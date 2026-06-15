"""
Glue Job (PySpark) — Módulo 06.

Lê os JSONs brutos do Bolsa Família na camada RAW, achata a estrutura
aninhada, normaliza tipos e grava em Parquet na camada CURATED,
particionado por ano/mes. O resultado é catalogado para o Athena
(Módulo 08) consultar — via Crawler (Módulo 07) ou DDL manual.

RAW     : s3://BUCKET/raw/bolsa_familia/ano=*/mes=*/uf=*/municipio=*.json
CURATED : s3://BUCKET/curated/bolsa_familia/ano=*/mes=*/  (Parquet)

Parâmetros do Job (--KEY value):
  --BUCKET   nome do bucket S3

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
job.commit()

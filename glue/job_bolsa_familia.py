"""
Glue Job (PySpark) — Módulo 06.

Lê os JSONs brutos do Bolsa Família na camada RAW, achata a estrutura
aninhada, normaliza tipos e grava em Parquet na camada CURATED,
particionado por ano/mes. Ao final, o PRÓPRIO job registra as partições
novas no Glue Data Catalog (ALTER TABLE ... ADD PARTITION) — sem crawler
e sem MSCK manual. Assim o Athena (Módulo 08) já enxerga os dados.

RAW     : s3://BUCKET/raw/bolsa_familia/ano=*/mes=*/uf=*/municipio=*.json
CURATED : s3://BUCKET/curated/bolsa_familia/ano=*/mes=*/  (Parquet)

Parâmetros do Job (--KEY value):
  --BUCKET   nome do bucket S3

Requer o Job parameter --enable-glue-datacatalog (faz o Spark usar o Glue
Data Catalog como metastore, habilitando o ALTER TABLE ADD PARTITION).
A tabela transparencia.bolsa_familia precisa existir (criada via DDL,
Módulo 08) — o job só ADICIONA partições, herdando o schema da tabela.

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
          f"crie via DDL no Modulo 08): {e}")

job.commit()

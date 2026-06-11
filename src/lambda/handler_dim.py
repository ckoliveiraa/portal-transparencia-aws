"""
Lambda DIM — ingestão da dimensão de municípios (IBGE) → S3.

100% na nuvem, sem upload manual (aw s3 cp). Faz 1 chamada à API de
Localidades do IBGE (sem chave, sem rate limit), achata a hierarquia e
grava o CSV direto no S3 via boto3.

Como a lista de municípios é praticamente estática, esta função roda
RARAMENTE (uma vez, ou anualmente) — diferente do worker dos fatos.

Saída: s3://BUCKET/raw/dim_municipios/dim_municipios.csv  (5.571 linhas)

Variáveis de ambiente:
  BUCKET   nome do bucket S3

Evento: nenhum parâmetro necessário (pode ser {} ).
"""

from __future__ import annotations

import csv
import io
import os

import boto3
import requests

IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
DIM_KEY = "raw/dim_municipios/dim_municipios.csv"

COLUNAS = [
    "codigo_ibge", "municipio", "uf_sigla", "uf_nome", "uf_codigo",
    "regiao_sigla", "regiao_nome", "mesorregiao", "microrregiao",
]

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]


def achatar(m: dict) -> dict:
    """Achata a hierarquia do IBGE. Municípios novos têm microrregiao=null;
    nesses casos a UF vem da hierarquia nova (regiao-imediata)."""
    micro = m.get("microrregiao")
    if micro:
        meso = micro["mesorregiao"]
        uf = meso["UF"]
        meso_nome, micro_nome = meso["nome"], micro["nome"]
    else:
        uf = m["regiao-imediata"]["regiao-intermediaria"]["UF"]
        meso_nome = micro_nome = ""
    regiao = uf["regiao"]
    return {
        "codigo_ibge": m["id"],
        "municipio": m["nome"],
        "uf_sigla": uf["sigla"],
        "uf_nome": uf["nome"],
        "uf_codigo": uf["id"],
        "regiao_sigla": regiao["sigla"],
        "regiao_nome": regiao["nome"],
        "mesorregiao": meso_nome,
        "microrregiao": micro_nome,
    }


def handler(event, context):
    resp = requests.get(IBGE_URL, headers={"accept": "application/json"}, timeout=60)
    resp.raise_for_status()
    municipios = resp.json()

    linhas = [achatar(m) for m in municipios]
    linhas.sort(key=lambda r: (r["uf_sigla"], r["municipio"]))

    # monta o CSV em memória e envia direto ao S3 (sem disco local)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUNAS)
    writer.writeheader()
    writer.writerows(linhas)

    s3.put_object(
        Bucket=BUCKET,
        Key=DIM_KEY,
        Body=buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )

    resultado = {"municipios": len(linhas), "destino": f"s3://{BUCKET}/{DIM_KEY}"}
    print(resultado)
    return resultado

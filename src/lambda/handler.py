"""
Lambda WORKER em lotes — ingestão dos fatos (Novo Bolsa Família) via API.

Módulo 04. Porta o coletor local (src/ingestao_api.py) para a nuvem:
a função de chamada à API é a mesma; muda o destino (S3 via boto3) e
ganha CHECKPOINT + TIME BUDGET para fechar os 5.571 municípios em
vários lotes (Lambda tem teto de 15 min).

Fluxo de uma invocação:
  1. lê o evento {ano, mes}
  2. lê a dim (lista de trabalho) do S3: raw/dim_municipios/dim_municipios.csv
  3. lê o checkpoint do mês (próximo offset) em _checkpoints/AAAAMM.json
  4. processa um LOTE respeitando 30 req/min, até acabar o time budget
  5. grava cada município em raw/bolsa_familia/ano=/mes=/uf=/municipio=COD.json
     (IDEMPOTENTE: HeadObject antes de chamar a API; se já existe, pula)
  6. salva o novo checkpoint; se terminou os 5.571, grava _SUCCESS
  7. retorna o progresso

Variáveis de ambiente:
  BUCKET            nome do bucket S3
  SECRET_NAME       nome do segredo no Secrets Manager (chave-api-dados)
  INTERVALO_SEG     intervalo entre chamadas (padrão 2.1 => <=30/min)
  MARGEM_SEG        segundos de folga antes do timeout p/ salvar checkpoint (padrão 30)

EventBridge re-invoca a cada ~15 min até o mês fechar (idempotente).
"""

from __future__ import annotations

import csv
import io
import json
import os
import time

import boto3
import requests

BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"
ENDPOINT = "/novo-bolsa-familia-por-municipio"
MAX_TENTATIVAS = 5

s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager")

BUCKET = os.environ["BUCKET"]
SECRET_NAME = os.environ.get("SECRET_NAME", "portal-transparencia/chave-api-dados")
INTERVALO_SEG = float(os.environ.get("INTERVALO_SEG", "2.1"))
MARGEM_SEG = float(os.environ.get("MARGEM_SEG", "30"))

DIM_KEY = "raw/dim_municipios/dim_municipios.csv"

_chave_cache: str | None = None


def get_chave() -> str:
    """Lê a chave-api-dados do Secrets Manager (cacheada entre invocações quentes)."""
    global _chave_cache
    if _chave_cache:
        return _chave_cache
    resp = secrets.get_secret_value(SecretId=SECRET_NAME)
    segredo = resp["SecretString"]
    # aceita tanto string pura quanto JSON {"chave-api-dados": "..."}
    try:
        segredo = json.loads(segredo).get("chave-api-dados", segredo)
    except (json.JSONDecodeError, AttributeError):
        pass
    _chave_cache = segredo
    return _chave_cache


def carregar_municipios() -> list[dict]:
    """Carrega a dim (lista de trabalho) do S3."""
    obj = s3.get_object(Bucket=BUCKET, Key=DIM_KEY)
    texto = obj["Body"].read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(texto)))


def ler_checkpoint(mes_ano: str) -> int:
    """Retorna o offset salvo (ou 0 se não houver checkpoint)."""
    key = f"_checkpoints/{mes_ano}.json"
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(obj["Body"].read())["offset"]
    except s3.exceptions.NoSuchKey:
        return 0


def salvar_checkpoint(mes_ano: str, offset: int, total: int) -> None:
    s3.put_object(
        Bucket=BUCKET,
        Key=f"_checkpoints/{mes_ano}.json",
        Body=json.dumps({"offset": offset, "total": total}).encode("utf-8"),
    )


def ja_existe(key: str) -> bool:
    """IDEMPOTÊNCIA: True se o objeto já está no S3."""
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except s3.exceptions.ClientError:
        return False


def coletar_municipio(sessao: requests.Session, chave: str, mes_ano: str, codigo: str) -> list:
    """1 chamada à API com retry/backoff em 429. (Mesma lógica do coletor local.)"""
    url = f"{BASE_URL}{ENDPOINT}"
    params = {"mesAno": mes_ano, "codigoIbge": codigo, "pagina": 1}
    headers = {"accept": "*/*", "chave-api-dados": chave}
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resp = sessao.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            time.sleep(INTERVALO_SEG * (2 ** (tentativa - 1)))
            continue
        resp.raise_for_status()
    raise RuntimeError(f"429 persistente em {codigo}")


def handler(event, context):
    ano = int(event["ano"])
    mes = int(event["mes"])
    mes_ano = f"{ano}{mes:02d}"

    chave = get_chave()
    municipios = carregar_municipios()
    total = len(municipios)
    offset = ler_checkpoint(mes_ano)

    sessao = requests.Session()
    baixados = pulados = 0
    i = offset

    while i < total:
        # TIME BUDGET: para o lote com folga p/ salvar checkpoint antes do timeout
        if context.get_remaining_time_in_millis() / 1000 < (INTERVALO_SEG + MARGEM_SEG):
            break

        m = municipios[i]
        codigo, uf = m["codigo_ibge"], m["uf_sigla"]
        key = (f"raw/bolsa_familia/ano={ano}/mes={mes:02d}/uf={uf}"
               f"/municipio={codigo}.json")

        if ja_existe(key):
            pulados += 1
            i += 1
            continue

        dados = coletar_municipio(sessao, chave, mes_ano, codigo)
        s3.put_object(
            Bucket=BUCKET, Key=key,
            Body=json.dumps(dados, ensure_ascii=False).encode("utf-8"),
        )
        baixados += 1
        i += 1
        time.sleep(INTERVALO_SEG)  # rate limit

    salvar_checkpoint(mes_ano, i, total)

    concluido = i >= total
    if concluido:
        s3.put_object(
            Bucket=BUCKET,
            Key=f"raw/bolsa_familia/ano={ano}/mes={mes:02d}/_SUCCESS",
            Body=b"",
        )

    resultado = {
        "mes_ano": mes_ano, "total": total, "offset_final": i,
        "baixados": baixados, "pulados": pulados, "concluido": concluido,
    }
    print(json.dumps(resultado))
    return resultado

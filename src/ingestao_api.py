"""
Coletor LOCAL da API do Portal da Transparência (Novo Bolsa Família).

Este é o script do Módulo 01 (ingestão local). Ele é deliberadamente
estruturado para virar a Lambda do Módulo 04 com mudança mínima:
a função `coletar_municipio()` é idêntica; só muda "onde gravar"
(disco local aqui; S3 via boto3 na Lambda).

Conceitos demonstrados:
  - autenticação por header (chave-api-dados)
  - rate limit (1 req a cada ~0,34s => <= 180/min, API restrita)
  - retry com backoff em caso de 429 (Too Many Requests)
  - idempotência (pula município cujo JSON já existe)
  - particionamento estilo data lake: ano=/mes=/uf=

Uso:
  python src/ingestao_api.py --ano 2026 --mes 4                # país inteiro (~30 min)
  python src/ingestao_api.py --ano 2026 --mes 4 --limite 5     # teste rápido
  python src/ingestao_api.py --ano 2026 --mes 4 --uf SP        # só uma UF
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests

# ----------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DIM_CSV = RAIZ / "data" / "dim_municipios.csv"
RAW_DIR = RAIZ / "data" / "raw" / "bolsa_familia"

BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"
ENDPOINT = "/novo-bolsa-familia-por-municipio"

# A 180 req/min (API restrita) o intervalo mínimo é ~0,33s; usamos 0,34s de margem.
INTERVALO_SEG = 0.34
MAX_TENTATIVAS = 5  # tentativas em caso de 429 / erro transitório


def carregar_chave() -> str:
    """Lê PORTAL_TRANSPARENCIA_API_KEY do ambiente ou do arquivo .env local."""
    import os

    chave = os.environ.get("PORTAL_TRANSPARENCIA_API_KEY")
    if chave:
        return chave

    env_path = RAIZ / ".env"
    if env_path.exists():
        for linha in env_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha.startswith("#") or "=" not in linha:
                continue
            nome, _, valor = linha.partition("=")
            if nome.strip() == "PORTAL_TRANSPARENCIA_API_KEY":
                return valor.strip()

    sys.exit("ERRO: defina PORTAL_TRANSPARENCIA_API_KEY no ambiente ou no .env")


def carregar_municipios(uf_filtro: str | None) -> list[dict]:
    """Lê a dim de municípios (lista de trabalho). Opcionalmente filtra por UF."""
    if not DIM_CSV.exists():
        sys.exit(f"ERRO: dim não encontrada em {DIM_CSV}. Rode build_dim_municipios.py antes.")
    with DIM_CSV.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if uf_filtro:
        linhas = [m for m in linhas if m["uf_sigla"] == uf_filtro.upper()]
    return linhas


def caminho_saida(ano: int, mes: int, uf: str, codigo: str) -> Path:
    """Caminho particionado estilo data lake — espelha o layout do S3."""
    return RAW_DIR / f"ano={ano}" / f"mes={mes:02d}" / f"uf={uf}" / f"municipio={codigo}.json"


def coletar_municipio(sessao: requests.Session, chave: str, mes_ano: str, codigo: str) -> list:
    """Faz 1 chamada à API para um município/mês. Trata 429 com backoff.

    Esta função é o "coração portável": vai para a Lambda sem alteração.
    """
    url = f"{BASE_URL}{ENDPOINT}"
    params = {"mesAno": mes_ano, "codigoIbge": codigo, "pagina": 1}
    headers = {"accept": "*/*", "chave-api-dados": chave}

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resp = sessao.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            espera = INTERVALO_SEG * (2 ** (tentativa - 1))  # backoff exponencial
            print(f"  429 (rate limit) em {codigo}; aguardando {espera:.1f}s "
                  f"(tentativa {tentativa}/{MAX_TENTATIVAS})")
            time.sleep(espera)
            continue
        resp.raise_for_status()  # outros erros: estoura
    raise RuntimeError(f"Falha em {codigo} após {MAX_TENTATIVAS} tentativas (429 persistente)")


def main() -> int:
    p = argparse.ArgumentParser(description="Coletor Bolsa Família por município")
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True, choices=range(1, 13))
    p.add_argument("--uf", help="filtra por UF (ex.: SP); padrão = todas")
    p.add_argument("--limite", type=int, help="processa só os N primeiros (teste)")
    args = p.parse_args()

    chave = carregar_chave()
    mes_ano = f"{args.ano}{args.mes:02d}"
    municipios = carregar_municipios(args.uf)
    if args.limite:
        municipios = municipios[: args.limite]

    total = len(municipios)
    print(f"Coletando {total} municípios para {mes_ano} "
          f"(intervalo {INTERVALO_SEG}s, ~{total * INTERVALO_SEG / 60:.0f} min)")

    sessao = requests.Session()
    baixados = pulados = vazios = 0

    for i, m in enumerate(municipios, start=1):
        codigo, uf = m["codigo_ibge"], m["uf_sigla"]
        destino = caminho_saida(args.ano, args.mes, uf, codigo)

        # IDEMPOTÊNCIA: se já baixamos, pula (não gasta chamada)
        if destino.exists():
            pulados += 1
            continue

        dados = coletar_municipio(sessao, chave, mes_ano, codigo)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

        if dados:
            baixados += 1
        else:
            vazios += 1  # município sem registro no mês (array vazio)

        if i % 50 == 0 or i == total:
            print(f"  {i}/{total} | baixados={baixados} pulados={pulados} vazios={vazios}")

        # RATE LIMIT: respeita o intervalo entre chamadas reais
        time.sleep(INTERVALO_SEG)

    print(f"OK -> {RAW_DIR}  (baixados={baixados}, pulados={pulados}, vazios={vazios})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Constrói a dimensão de municípios (dim_municipios) a partir da
API de Localidades do IBGE — fonte oficial dos códigos IBGE.

Saída: data/dim_municipios.csv  (5.571 municípios)

Não exige chave de API. Uma única requisição traz todos os municípios.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import requests

IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "dim_municipios.csv"

COLUNAS = [
    "codigo_ibge",
    "municipio",
    "uf_sigla",
    "uf_nome",
    "uf_codigo",
    "regiao_sigla",
    "regiao_nome",
    "mesorregiao",
    "microrregiao",
]


def achatar(m: dict) -> dict:
    """Achata a hierarquia aninhada do IBGE em uma linha plana.

    Alguns municípios novos têm `microrregiao = null` (classificação
    micro/meso descontinuada pelo IBGE). Nesses casos a UF é obtida pela
    hierarquia nova (regiao-imediata -> regiao-intermediaria -> UF).
    """
    micro = m.get("microrregiao")
    if micro:  # hierarquia antiga (micro/meso) disponível
        meso = micro["mesorregiao"]
        uf = meso["UF"]
        meso_nome = meso["nome"]
        micro_nome = micro["nome"]
    else:  # fallback pela hierarquia nova
        uf = m["regiao-imediata"]["regiao-intermediaria"]["UF"]
        meso_nome = ""
        micro_nome = ""

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


def main() -> int:
    print(f"Baixando municípios do IBGE: {IBGE_URL}")
    resp = requests.get(IBGE_URL, headers={"accept": "application/json"}, timeout=60)
    resp.raise_for_status()
    municipios = resp.json()
    print(f"  {len(municipios)} municípios recebidos")

    linhas = [achatar(m) for m in municipios]
    # ordena por UF e nome para facilitar leitura
    linhas.sort(key=lambda r: (r["uf_sigla"], r["municipio"]))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUNAS)
        writer.writeheader()
        writer.writerows(linhas)

    print(f"OK -> {OUTPUT}  ({len(linhas)} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

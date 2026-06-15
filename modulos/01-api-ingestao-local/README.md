# Módulo 01 — A API e a chave (ingestão local)

## 🎯 Objetivo
Conhecer a **API do Portal da Transparência**, **cadastrar-se no gov.br para obter a chave
de acesso**, fazer a primeira chamada e rodar o **coletor local** em Python que será a base
da nossa Lambda mais à frente.

## 🧠 Conceitos
- **API REST**: você faz uma requisição HTTP (`GET`) a uma URL e recebe dados (JSON) de volta.
- **Autenticação por chave (API key)**: a API exige um header `chave-api-dados` para identificar quem chama.
- **Rate limit**: limite de quantas requisições você pode fazer por minuto.
- **Paginação**: quando há muitos resultados, eles vêm em "páginas".
- **Dimensão (dim)**: tabela de referência (aqui, os municípios do IBGE) usada para enriquecer os fatos.

---

## 📚 Parte A — Apresentando a API

O **Portal da Transparência** publica gastos e benefícios do governo federal. Usaremos o
programa **Novo Bolsa Família por município**.

- **Documentação interativa (Swagger):**
  https://api.portaldatransparencia.gov.br/swagger-ui/index.html
- **Base URL:** `https://api.portaldatransparencia.gov.br/api-de-dados`
- **Endpoint do curso:** `GET /novo-bolsa-familia-por-municipio`

| Parâmetro | Obrigatório | Exemplo | Descrição |
|-----------|:-----------:|---------|-----------|
| `mesAno` | ✅ | `202401` | Ano + mês (AAAAMM) |
| `codigoIbge` | ✅ | `3550308` | Código IBGE do município |
| `pagina` | ❌ | `1` | Página (padrão 1) |

Mais detalhes em [`docs/api-endpoints.md`](../../docs/api-endpoints.md) e os limites em
[`docs/api-limites.md`](../../docs/api-limites.md).

---

## 🔑 Parte B — Como cadastrar e obter sua chave (passo a passo)

A chave é **gratuita** e sai na hora.

1. **Acesse a página de cadastro:**
   👉 https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email
2. **Faça login com a conta gov.br.**
   - O Portal exige autenticação **gov.br** (mesma conta de CPF usada em outros serviços do governo).
   - Não tem conta? Crie em https://acesso.gov.br (precisa de CPF; o nível *bronze* já serve).
3. **Confirme o e-mail / gere o token.**
   - Após o login, o Portal gera um **token (a `chave-api-dados`)** vinculado à sua conta.
   - É uma string longa (ex.: `0c2edd2dce68b77258f713fb2130b602`).
4. **Guarde a chave com segurança.** Copie para o arquivo `.env` na raiz do projeto:
   ```env
   PORTAL_TRANSPARENCIA_API_KEY=sua_chave_aqui
   ```
   > ⚠️ O `.env` está no `.gitignore` — a chave **nunca** vai para o Git. No Módulo 03 ela migra para o AWS Secrets Manager.

### Primeira chamada (teste rápido com curl)
```bash
curl "https://api.portaldatransparencia.gov.br/api-de-dados/novo-bolsa-familia-por-municipio?mesAno=202401&codigoIbge=3550308&pagina=1" \
  -H "chave-api-dados: SUA_CHAVE"
```
- **Sem a chave** → `401 - Chave de API não informada`.
- **Com a chave** → `200` e um JSON com o valor pago e o nº de beneficiários de São Paulo.

---

## 🪜 Parte C — Ingestão local em Python

Com a chave no `.env`, vamos coletar de verdade.

1. **Ambiente e dependências:**
   ```bash
   python -m venv .venv
   ./.venv/Scripts/python.exe -m pip install -r src/lambda/requirements.txt
   ```
2. **Gerar a dimensão de municípios** (1 chamada ao IBGE, sem chave):
   ```bash
   ./.venv/Scripts/python.exe src/build_dim_municipios.py
   # -> data/dim_municipios.csv (5.571 municípios)
   ```
3. **Coletar os fatos** (Bolsa Família) — comece pequeno para não esperar 3h:
   ```bash
   # 5 municípios de SP, ~10s
   ./.venv/Scripts/python.exe src/ingestao_api.py --ano 2024 --mes 1 --uf SP --limite 5
   ```
   Os arquivos saem em `data/raw/bolsa_familia/ano=2024/mes=01/uf=SP/municipio=*.json`
   (o mesmo layout particionado que usaremos no S3).

> 🔎 Abra `src/ingestao_api.py`: repare no **intervalo de 2,1s** (rate limit), no **retry em 429**
> e no **skip de arquivos já baixados** (idempotência). Esses três conceitos reaparecem na Lambda.

## 🧩 O código (para copiar)

<details>
<summary>📄 <code>src/build_dim_municipios.py</code> — gera a dim de municípios (IBGE)</summary>

```python
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
```

</details>

<details>
<summary>📄 <code>src/ingestao_api.py</code> — coletor local dos fatos (Bolsa Família)</summary>

```python
"""
Coletor LOCAL da API do Portal da Transparência (Novo Bolsa Família).

Este é o script do Módulo 01 (ingestão local). Ele é deliberadamente
estruturado para virar a Lambda do Módulo 04 com mudança mínima:
a função `coletar_municipio()` é idêntica; só muda "onde gravar"
(disco local aqui; S3 via boto3 na Lambda).

Conceitos demonstrados:
  - autenticação por header (chave-api-dados)
  - rate limit (1 req a cada ~2,1s => <= 30/min)
  - retry com backoff em caso de 429 (Too Many Requests)
  - idempotência (pula município cujo JSON já existe)
  - particionamento estilo data lake: ano=/mes=/uf=

Uso:
  python src/ingestao_api.py --ano 2024 --mes 1                # país inteiro (~3h)
  python src/ingestao_api.py --ano 2024 --mes 1 --limite 5     # teste rápido
  python src/ingestao_api.py --ano 2024 --mes 1 --uf SP        # só uma UF
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

# A 30 req/min o intervalo mínimo é 2,0s; usamos 2,1s de margem.
INTERVALO_SEG = 2.1
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
```

</details>

## 🔍 Validação
- `data/dim_municipios.csv` tem 5.571 linhas (+1 cabeçalho).
- Os JSONs aparecem na estrutura `ano=/mes=/uf=/municipio=`.
- Rodar o mesmo comando de novo mostra `pulados=5` (idempotência funcionando).

## 💲 Custos / Free Tier
- **Zero** — tudo roda na sua máquina. A API e o IBGE são gratuitos.

## 🧹 Limpeza
- Nada na AWS ainda. Para limpar local: apague `data/raw/`.

➡️ Próximo: [Módulo 02 — S3 / Data Lake](../02-s3-data-lake/README.md)

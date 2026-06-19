# Módulo 04 — Lambda (worker em lotes)

## 🎯 Objetivo
Levar o coletor local para a nuvem como uma **Lambda** que ingere os fatos em **lotes**,
gravando no S3, com **checkpoint**, **idempotência** e **retry de rate limit**.

## 🧠 Conceitos
- **Lambda**: roda código sem servidor; você paga por execução. **Teto de 15 min** por invocação.
- **IAM Role da Lambda**: identidade que dá permissões à função (ler segredo, escrever no S3).
- **Lambda Layer**: pacote com dependências (aqui, `requests`); `boto3` já vem no runtime.
- **Variáveis de ambiente**: configuram a função sem mudar o código (`BUCKET`, `SECRET_NAME`...).
- **Por que lotes**: 5.571 chamadas × ~0,34s ≈ ~32 min > 15 min. Logo, cada invocação faz um pedaço e **retoma** depois.

## ✅ Pré-requisitos
- Módulos 02 (bucket + dim no S3) e 03 (segredo).

## 🧩 O código (já pronto)
`src/lambda/handler.py` — destaques:
- `get_chave()` lê do Secrets Manager (cache entre execuções quentes).
- `ler_checkpoint()/salvar_checkpoint()` controlam o **offset** em `_checkpoints/AAAAMM.json`.
- `ja_existe()` faz `HeadObject` → **idempotência**.
- `coletar_municipio()` chama a API com **retry/backoff** em `429`.
- **Time budget**: `context.get_remaining_time_in_millis()` para parar antes do timeout e salvar o checkpoint.
- Ao terminar os 5.571, grava `_SUCCESS` e retorna `concluido: true` — é esse campo que o
  **Step Functions** (Módulo 06) usa para saber que pode parar o loop e seguir pro Glue.

<details>
<summary>📄 <code>src/lambda/handler.py</code> — código completo (clique para copiar)</summary>

```python
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
  4. processa um LOTE respeitando ~180 req/min, até acabar o time budget
  5. grava cada município em raw/bolsa_familia/ano=/mes=/uf=/municipio=COD.json
     (IDEMPOTENTE: HeadObject antes de chamar a API; se já existe, pula)
  6. salva o novo checkpoint; se terminou os 5.571, grava _SUCCESS
  7. retorna o progresso (com `concluido`) para o orquestrador decidir o próximo passo

Variáveis de ambiente:
  BUCKET            nome do bucket S3
  SECRET_NAME       nome do segredo no Secrets Manager (chave-api-dados)
  INTERVALO_SEG     intervalo entre chamadas (padrão 0.34 => <=180/min)
  MARGEM_SEG        segundos de folga antes do timeout p/ salvar checkpoint (padrão 30)

Quem reinvoca em lote até o mês fechar é o Step Functions (um Choice no `concluido`),
que para sozinho ao concluir e então dispara o Glue (idempotente — seguro reinvocar).
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
INTERVALO_SEG = float(os.environ.get("INTERVALO_SEG", "0.34"))
MARGEM_SEG = float(os.environ.get("MARGEM_SEG", "30"))
# Backoff ao estourar o limite (429): base maior que o INTERVALO p/ limpar a janela de 1 min.
BACKOFF_429_SEG = float(os.environ.get("BACKOFF_429_SEG", "5"))

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
            # honra Retry-After (segundos) se vier; senão, backoff exponencial
            espera = float(resp.headers.get("Retry-After",
                                            BACKOFF_429_SEG * (2 ** (tentativa - 1))))
            time.sleep(espera)
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
```

</details>

<details>
<summary>📄 <code>src/lambda/handler_dim.py</code> — código completo (clique para copiar)</summary>

```python
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
```

</details>

## 🔐 IAM — policies (prontas para copiar)
Cada Lambda tem sua role: trust comum (`lambda.amazonaws.com`) + a managed
`AWSLambdaBasicExecutionRole` (logs) + a inline abaixo (arquivos em [`iam/`](../../iam/);
troque `<projectname>` e `<conta>`).

<details>
<summary>📄 <code>iam/lambda-trust-policy.json</code> — trust (vale p/ <code>transparencia-ingestao-worker-role</code> e <code>transparencia-ingestao-dim-role</code>)</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

</details>

<details>
<summary>📄 <code>iam/worker-role-policy.json</code> — inline <code>worker-s3-secrets</code> da role <code>transparencia-ingestao-worker-role</code> (S3 + Secrets)</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Objetos",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>/*"
    },
    {
      "Sid": "S3ListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>"
    },
    {
      "Sid": "LerSegredo",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:<conta>:secret:portal-transparencia/chave-api-dados-*"
    }
  ]
}
```

</details>

<details>
<summary>📄 <code>iam/dim-role-policy.json</code> — inline <code>dim-s3-put</code> da role <code>transparencia-ingestao-dim-role</code> (só grava a dim)</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GravarDim",
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>/raw/dim_municipios/*"
    }
  ]
}
```

</details>

## 🪜 Passo a passo (console)
> Runtime do curso: **Python 3.14** em todas as Lambdas.

1. **A Layer do `requests`** (o `boto3` já vem no runtime; o `requests` **não**). Dois caminhos —
   usamos o **A** (empacotar a nossa ensina como uma Layer funciona por dentro):
   - **A) Construir a sua (o que fazemos)**:
     ```bash
     mkdir -p layer/python
     ./.venv/Scripts/python.exe -m pip install requests -t layer/python
     cd layer && zip -r ../requests-layer.zip python && cd ..
     ```
     Lambda → *Layers* → *Create layer* → suba `requests-layer.zip` → runtime **Python 3.14**.
   - **B) Layer pública Klayers (opção — bom de conhecer)** — não empacota nada, é só informar
     o ARN (Python 3.14, us-east-1):
     ```
     arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p314-requests:5
     ```
2. **Criar a função**: Lambda → *Create function* → *Author from scratch* → **Python 3.14**.
   - Cole o conteúdo de `src/lambda/handler.py`; handler = `handler.handler`.
   - **Layers → Add a layer:** *Custom layers* (a sua, 1A) **ou** *Specify an ARN* (Klayers, 1B).
3. **Configurar**:
   - *Timeout*: **15 min**; *Memory*: 256 MB.
   - *Environment variables*:
     | Key | Value |
     |-----|-------|
     | `BUCKET` | `transparencia-datalake-us-east-1-<projectname>` |
     | `SECRET_NAME` | `portal-transparencia/chave-api-dados` |
4. **Permissões (IAM Role `transparencia-ingestao-worker-role`)** — inline `worker-s3-secrets`
   ([`iam/worker-role-policy.json`](../../iam/worker-role-policy.json); trust em
   [`iam/lambda-trust-policy.json`](../../iam/lambda-trust-policy.json)) com:
   - `s3:GetObject`, `s3:PutObject` no `arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>/*` (objetos);
   - **`s3:ListBucket`** no `arn:aws:s3:::transparencia-datalake-us-east-1-<projectname>` (o bucket, **sem** `/*`);
   - `secretsmanager:GetSecretValue` no ARN do segredo;
   - logs no CloudWatch (já vem no `AWSLambdaBasicExecutionRole`).
   > 💡 Quem reinvoca o worker em lote é o **Step Functions** (Módulo 06) — a permissão de
   > `lambda:InvokeFunction` fica na role da máquina de estados, não aqui.
   > ⚠️ **Gotcha real:** sem `s3:ListBucket`, um `GetObject` num objeto que **ainda não existe**
   > (o checkpoint na 1ª execução) retorna **`AccessDenied`** em vez de **`NoSuchKey`** — e o código
   > quebra, porque ele espera `NoSuchKey` para "começar do zero". A cura é exatamente esse
   > `s3:ListBucket` no ARN do **bucket**.
5. **Criar TAMBÉM a Lambda da dim** (`handler_dim.py`) — popula os municípios sem `cp`:
   - mesma Layer; handler = `handler_dim.handler`; **Timeout 120s** ⚠️ (a dim chama o IBGE com
     `timeout=60`; os **3s** padrão do console não cabem). Memory 256 MB.
   - role: pode reusar a do worker (já tem `PutObject`) ou uma própria
     `transparencia-ingestao-dim-role` com a inline `dim-s3-put` só com `s3:PutObject` em
     `raw/dim_municipios/*` ([`iam/dim-role-policy.json`](../../iam/dim-role-policy.json)).
     env var: `BUCKET` (não precisa de `SECRET_NAME`, a API do IBGE é aberta).
6. **Ordem de execução importa** — o worker lê a dim do S3, então rode a dim **primeiro**:
   ```bash
   # 6a) popula a dimensão (1 chamada IBGE -> S3)
   aws lambda invoke --function-name transparencia-ingestao-dim \
     --payload '{}' --cli-binary-format raw-in-base64-out dim.json && cat dim.json
   ```
7. **Testar o worker** com o evento `{ "ano": 2026, "mes": 4 }`:
   A primeira execução processa ~2.500 municípios e salva o checkpoint.

## 🔍 Validação
- O retorno mostra `baixados`, `offset_final` e `concluido: false` (ainda faltam municípios).
- `aws s3 ls s3://.../raw/bolsa_familia/ano=2026/mes=04/ --recursive` mostra JSONs novos.
- `aws s3 cp s3://.../_checkpoints/202604.json -` mostra o offset salvo.
- Rodar de novo **continua** de onde parou (e pula os já baixados).

## 💲 Custos / Free Tier
- Lambda: **1M requisições/mês grátis** + 400k GB-s. Nossas ~14 invocações/mês → **zero**.

## 🧹 Limpeza
- A função fica para os Módulos 05–06. Para apagar: Lambda → *Delete function* (faremos no Módulo 09).

➡️ Próximo: [Módulo 05 — Glue (transformação com PySpark)](../05-glue-transformacao/README.md)

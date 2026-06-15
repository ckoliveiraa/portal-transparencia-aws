# Módulo 04 — Lambda (worker em lotes)

## 🎯 Objetivo
Levar o coletor local para a nuvem como uma **Lambda** que ingere os fatos em **lotes**,
gravando no S3, com **checkpoint**, **idempotência** e **retry de rate limit**.

## 🧠 Conceitos
- **Lambda**: roda código sem servidor; você paga por execução. **Teto de 15 min** por invocação.
- **IAM Role da Lambda**: identidade que dá permissões à função (ler segredo, escrever no S3).
- **Lambda Layer**: pacote com dependências (aqui, `requests`); `boto3` já vem no runtime.
- **Variáveis de ambiente**: configuram a função sem mudar o código (`BUCKET`, `SECRET_NAME`...).
- **Por que lotes**: 5.571 chamadas × ~2s = ~3h > 15 min. Logo, cada invocação faz um pedaço e **retoma** depois.

## ✅ Pré-requisitos
- Módulos 02 (bucket + dim no S3) e 03 (segredo).

## 🧩 O código (já pronto)
`src/lambda/handler.py` — destaques:
- `get_chave()` lê do Secrets Manager (cache entre execuções quentes).
- `ler_checkpoint()/salvar_checkpoint()` controlam o **offset** em `_checkpoints/AAAAMM.json`.
- `ja_existe()` faz `HeadObject` → **idempotência**.
- `coletar_municipio()` chama a API com **retry/backoff** em `429`.
- **Time budget**: `context.get_remaining_time_in_millis()` para parar antes do timeout e salvar o checkpoint.
- Ao terminar os 5.571, grava `_SUCCESS`.

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
   - *Environment variables*: `BUCKET=transparencia-datalake-us-east-1-training`, `SECRET_NAME=portal-transparencia/chave-api-dados`.
4. **Permissões (IAM Role `transparencia-ingestao-worker-role`)** — policy inline com:
   - `s3:GetObject`, `s3:PutObject` no `arn:aws:s3:::transparencia-datalake-us-east-1-training/*` (objetos);
   - **`s3:ListBucket`** no `arn:aws:s3:::transparencia-datalake-us-east-1-training` (o bucket, **sem** `/*`);
   - `secretsmanager:GetSecretValue` no ARN do segredo;
   - logs no CloudWatch (já vem no `AWSLambdaBasicExecutionRole`).
   > ⚠️ **Gotcha real:** sem `s3:ListBucket`, um `GetObject` num objeto que **ainda não existe**
   > (o checkpoint na 1ª execução) retorna **`AccessDenied`** em vez de **`NoSuchKey`** — e o código
   > quebra, porque ele espera `NoSuchKey` para "começar do zero". A cura é exatamente esse
   > `s3:ListBucket` no ARN do **bucket**.
5. **Criar TAMBÉM a Lambda da dim** (`handler_dim.py`) — popula os municípios sem `cp`:
   - mesma Layer; handler = `handler_dim.handler`; **Timeout 120s** ⚠️ (a dim chama o IBGE com
     `timeout=60`; os **3s** padrão do console não cabem). Memory 256 MB.
   - role: pode reusar a do worker (já tem `PutObject`) ou uma própria só com `s3:PutObject` em
     `raw/dim_municipios/*`. env var: `BUCKET` (não precisa de `SECRET_NAME`, a API do IBGE é aberta).
6. **Ordem de execução importa** — o worker lê a dim do S3, então rode a dim **primeiro**:
   ```bash
   # 6a) popula a dimensão (1 chamada IBGE -> S3)
   aws lambda invoke --function-name transparencia-ingestao-dim \
     --payload '{}' --cli-binary-format raw-in-base64-out dim.json && cat dim.json
   ```
7. **Testar o worker** com o evento `{ "ano": 2024, "mes": 1 }`:
   A primeira execução processa ~400 municípios e salva o checkpoint.

## 🔍 Validação
- O retorno mostra `baixados`, `offset_final` e `concluido: false` (ainda faltam municípios).
- `aws s3 ls s3://.../raw/bolsa_familia/ano=2024/mes=01/ --recursive` mostra JSONs novos.
- `aws s3 cp s3://.../_checkpoints/202401.json -` mostra o offset salvo.
- Rodar de novo **continua** de onde parou (e pula os já baixados).

## 🏋️ Exercícios
1. Invoque manualmente várias vezes até ver `concluido: true` e o `_SUCCESS`.
2. Reduza o timeout para 1 min e observe lotes menores (mais invocações).
3. Veja os logs em CloudWatch → Log groups → `/aws/lambda/...`.

## 💲 Custos / Free Tier
- Lambda: **1M requisições/mês grátis** + 400k GB-s. Nossas ~14 invocações/mês → **zero**.

## 🧹 Limpeza
- A função fica para o Módulo 05. Para apagar: Lambda → *Delete function* (faremos no Módulo 09).

➡️ Próximo: [Módulo 05 — EventBridge](../05-eventbridge-agenda/README.md)

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
1. **Criar a Layer do `requests`**:
   ```bash
   mkdir -p layer/python
   ./.venv/Scripts/python.exe -m pip install requests -t layer/python
   cd layer && zip -r ../requests-layer.zip python && cd ..
   ```
   Lambda → *Layers* → *Create layer* → suba `requests-layer.zip` → runtime Python 3.12.
2. **Criar a função**: Lambda → *Create function* → *Author from scratch* → Python 3.12.
   - Cole o conteúdo de `src/lambda/handler.py`; handler = `handler.handler`.
   - Anexe a Layer criada.
3. **Configurar**:
   - *Timeout*: **15 min**; *Memory*: 256 MB.
   - *Environment variables*: `BUCKET=transparencia-datalake-SEUNOME`, `SECRET_NAME=portal-transparencia/chave-api-dados`.
4. **Permissões (IAM Role)** — anexe uma policy com:
   - `s3:GetObject`, `s3:PutObject`, `s3:HeadObject` no seu bucket;
   - `secretsmanager:GetSecretValue` no seu segredo;
   - logs no CloudWatch (já vem no role básico).
5. **Criar TAMBÉM a Lambda da dim** (`handler_dim.py`) — popula os municípios sem `cp`:
   - mesma role e mesma Layer; handler = `handler_dim.handler`; timeout 60s.
   - env var: `BUCKET` (não precisa de `SECRET_NAME`, a API do IBGE é aberta).
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
- A função fica para o Módulo 05. Para apagar: Lambda → *Delete function* (faremos no Módulo 10).

➡️ Próximo: [Módulo 05 — EventBridge](../05-eventbridge-agenda/README.md)

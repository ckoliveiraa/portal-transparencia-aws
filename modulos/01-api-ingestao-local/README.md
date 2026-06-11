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

## 🔍 Validação
- `data/dim_municipios.csv` tem 5.571 linhas (+1 cabeçalho).
- Os JSONs aparecem na estrutura `ano=/mes=/uf=/municipio=`.
- Rodar o mesmo comando de novo mostra `pulados=5` (idempotência funcionando).

## 🏋️ Exercícios
1. Colete o estado inteiro de SP (sem `--limite`) e cronometre.
2. Mude o mês para `--mes 2` e veja o novo particionamento.
3. Tente sem a chave no `.env` e observe o erro `401`.

## 💲 Custos / Free Tier
- **Zero** — tudo roda na sua máquina. A API e o IBGE são gratuitos.

## 🧹 Limpeza
- Nada na AWS ainda. Para limpar local: apague `data/raw/`.

➡️ Próximo: [Módulo 02 — S3 / Data Lake](../02-s3-data-lake/README.md)

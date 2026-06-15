# Módulo 01 — As APIs e a chave

## 🎯 Objetivo
Conhecer as **duas APIs** que alimentam o projeto — a **API do Portal da Transparência**
(os fatos do Novo Bolsa Família) e a **API de Localidades do IBGE** (a dimensão de municípios) —
e **cadastrar-se no gov.br para obter a chave** do Portal. O código que consome essas APIs vira
a Lambda no Módulo 04; aqui o foco é **entender as fontes de dados**.

## 🧠 Conceitos
- **API REST**: você faz uma requisição HTTP (`GET`) a uma URL e recebe dados (JSON) de volta.
- **Autenticação por chave (API key)**: o Portal exige o header `chave-api-dados`. O IBGE é **aberto** (sem chave).
- **Rate limit**: limite de requisições por minuto — existe no Portal; o **IBGE não tem**.
- **Paginação**: quando há muitos resultados, eles vêm em "páginas".
- **Dimensão (dim)**: tabela de referência (os municípios do IBGE) usada para enriquecer os fatos
  e como **lista de trabalho** — os 5.571 `codigoIbge` que o coletor percorre.

---

## 📚 Parte A — A API do Portal da Transparência (os fatos)

O **Portal da Transparência** publica gastos e benefícios do governo federal. Usaremos o
programa **Novo Bolsa Família por município**.

- **Documentação interativa (Swagger):**
  https://api.portaldatransparencia.gov.br/swagger-ui/index.html
- **Base URL:** `https://api.portaldatransparencia.gov.br/api-de-dados`
- **Endpoint do curso:** `GET /novo-bolsa-familia-por-municipio`

| Parâmetro | Obrigatório | Exemplo | Descrição |
|-----------|:-----------:|---------|-----------|
| `mesAno` | ✅ | `202604` | Ano + mês (AAAAMM) |
| `codigoIbge` | ✅ | `3550308` | Código IBGE do município |
| `pagina` | ❌ | `1` | Página (padrão 1) |

Mais detalhes em [`docs/api-endpoints.md`](../../docs/api-endpoints.md) e os limites em
[`docs/api-limites.md`](../../docs/api-limites.md).

> 🔑 Repare: o `codigoIbge` é **obrigatório** — é 1 chamada por município. Quem nos dá a lista
> oficial desses códigos é a **API do IBGE** (Parte C).

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
curl "https://api.portaldatransparencia.gov.br/api-de-dados/novo-bolsa-familia-por-municipio?mesAno=202604&codigoIbge=3550308&pagina=1" \
  -H "chave-api-dados: SUA_CHAVE"
```
- **Sem a chave** → `401 - Chave de API não informada`.
- **Com a chave** → `200` e um JSON com o valor pago e o nº de beneficiários de São Paulo.

---

## 🗺️ Parte C — A API do IBGE (a dimensão de municípios)

A **segunda fonte** do projeto. Como o Portal exige o **`codigoIbge`** de cada município, precisamos
da lista oficial dos 5.571 municípios brasileiros. Quem fornece é a **API de Localidades do IBGE** —
pública, **sem chave e sem rate limit** (dados abertos).

- **Endpoint:** `GET https://servicodados.ibge.gov.br/api/v1/localidades/municipios`
- **Retorno:** um **array JSON com todos os municípios** numa **única requisição**, com a hierarquia
  aninhada (município → micro/mesorregião → UF → região).
- **Sem autenticação e sem limite** de requisições.

### Exemplo
```bash
curl "https://servicodados.ibge.gov.br/api/v1/localidades/municipios" \
  -H "accept: application/json"
```
Amostra (1 município, resumida):
```json
[
  {
    "id": 3550308,
    "nome": "São Paulo",
    "microrregiao": {
      "mesorregiao": {
        "UF": {
          "sigla": "SP", "nome": "São Paulo",
          "regiao": { "sigla": "SE", "nome": "Sudeste" }
        }
      }
    }
  }
]
```
O campo **`id`** é justamente o **código IBGE** que o Portal pede (`codigoIbge`).

### Da API para a dimensão (`dim_municipios`)
O script `src/build_dim_municipios.py` faz **1 chamada** ao IBGE, **achata** essa hierarquia em
colunas planas e produz a dim (5.571 linhas):

`codigo_ibge · municipio · uf_sigla · uf_nome · uf_codigo · regiao_sigla · regiao_nome · mesorregiao · microrregiao`

> 🔎 **Neste curso não rodamos a coleta localmente.** Esse mesmo código vira a **Lambda dim**
> (Módulo 04), que grava `dim_municipios` direto no **S3** — você verá o código lá. Aqui o objetivo
> é só **entender de onde vêm os dados** e por que precisamos de **duas** APIs.

> ⚠️ Detalhe real do IBGE: alguns municípios novos têm `microrregiao = null` (a classificação
> micro/mesorregião foi descontinuada). Nesses casos a UF vem pela hierarquia nova
> (`regiao-imediata → regiao-intermediaria → UF`) — o `build_dim` já trata isso.

## 🔍 Validação (entendimento)
- A chamada ao **Portal** (com a chave) retorna `200` com o valor pago + nº de beneficiários do município.
- A chamada ao **IBGE** retorna os **5.571 municípios** num único array.
- Você sabe explicar por que precisamos das **duas** APIs: o **IBGE** dá a *lista de códigos*; o
  **Portal** dá os *valores* por código.

## 💲 Custos / Free Tier
- **Zero** — as duas APIs são gratuitas e nada foi criado na AWS ainda.

## 🧹 Limpeza
- Nada a remover (nada criado localmente nem na AWS).

➡️ Próximo: [Módulo 02 — S3 / Data Lake](../02-s3-data-lake/README.md)

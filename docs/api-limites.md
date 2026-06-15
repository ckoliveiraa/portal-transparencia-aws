# Limites da API — Portal da Transparência

Limites operacionais da API de Dados, conforme a página oficial de cadastro/uso
([api-de-dados/cadastrar-email](https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email)).

## Rate limit (requisições por minuto)

Há um limite **geral** (varia por faixa de horário, horário de Brasília) e um limite menor para
**APIs restritas** (independe do horário):

| Tipo / faixa | Limite |
|--------------|--------|
| **Geral — 00h00 – 06h00** (madrugada) | **700 requisições/minuto** |
| **Geral — demais horários** | **400 requisições/minuto** |
| **APIs restritas** (qualquer horário) | **180 requisições/minuto** |

### APIs restritas (180/min)
São endpoints com dados mais sensíveis/pesados. A lista oficial inclui:
`despesas/documentos-por-favorecido`, `bolsa-familia-disponivel-por-cpf-ou-nis`,
`bolsa-familia-por-municipio`, `bolsa-familia-sacado-por-nis`,
`auxilio-emergencial-beneficiario-por-municipio`, `auxilio-emergencial-por-cpf-ou-nis`,
`auxilio-emergencial-por-municipio`, `seguro-defeso-codigo`.

> ⚠️ **Nosso endpoint** é `novo-bolsa-familia-por-municipio` (Novo Bolsa Família). Ele **não
> aparece literalmente** na lista de restritas (que cita o programa *antigo* `bolsa-familia-...`).
> Por segurança, o curso o trata como **restrito → 180 req/min** (pior caso). Se na prática a API
> aplicar o limite geral (400/700), só sobra folga.

### Ao estourar o limite
- A API responde com **HTTP `429 Too Many Requests`**.
- Estourar o limite pode levar à **suspensão temporária do token** — basta aguardar e retomar.
- Boa prática: implementar **retry com backoff exponencial** ao receber `429`.

## Paginação

| Aspecto | Detalhe |
|---------|---------|
| Parâmetro | `pagina` (inteiro, começa em `1`) |
| Registros por página | Geralmente **15**; alguns endpoints até ~500 |
| Fim dos dados | Resposta vem como array vazio `[]` |
| Estratégia | Iterar `pagina=1,2,3...` até resposta vazia |

## Cache (CloudFront)

- Respostas ficam em cache por **~2h** (`Cache-Control: max-age=7200`).
- Consultas **idênticas** retornam do cache (`X-Cache: Hit from cloudfront`) e
  **não contam** contra o rate limit.
- Útil para reprocessar/depurar sem gastar cota.

## Autenticação

- Header obrigatório: `chave-api-dados: <SUA_CHAVE>`
- 1 chave por conta **gov.br**.
- Sem limite diário total documentado — apenas o limite por minuto acima.
- Sem a chave: `HTTP 401 - Chave de API não informada`.

## Recomendações para coleta em lote

1. Respeitar o ritmo: como tratamos o endpoint como **restrito (180/min)**, usamos
   **~1 req / 0,34s** (≈176/min, com folga). Os 5.571 municípios saem em **~32 min**.
2. Tratar `429` com retry + backoff.
3. Aproveitar o cache para repetições.
4. Persistir o progresso (última página/município processado) para retomar.

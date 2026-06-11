# Limites da API — Portal da Transparência

Documentação dos limites operacionais da API de Dados, confirmados em **10/06/2026**.

## Rate limit (requisições por minuto)

Os limites variam por **faixa de horário (horário de Brasília)**:

| Faixa de horário | Limite |
|------------------|--------|
| **06h00 – 23h59** (dia) | **30 requisições/minuto** |
| **00h00 – 05h59** (madrugada) | **90 requisições/minuto** |

> A madrugada tem limite 3× maior para incentivar cargas pesadas/em lote fora do pico.

### Ao estourar o limite
- A API responde com **HTTP `429 Too Many Requests`**.
- Não há bloqueio permanente da chave — basta aguardar a virada do minuto e retomar.
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

1. Respeitar o ritmo: **~1 req / 2s** (≈30/min) no horário comercial;
   de madrugada pode subir para **~1 req / 0,7s** (≈90/min).
2. Tratar `429` com retry + backoff.
3. Aproveitar o cache para repetições.
4. Persistir o progresso (última página/município processado) para retomar.

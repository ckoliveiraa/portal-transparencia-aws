# Endpoints — Portal da Transparência

Base URL: `https://api.portaldatransparencia.gov.br/api-de-dados`

Documentação interativa (Swagger):
https://api.portaldatransparencia.gov.br/swagger-ui/index.html

Todas as chamadas exigem o header:
```
chave-api-dados: <SUA_CHAVE>
```

---

## Novo Bolsa Família por Município

`GET /novo-bolsa-familia-por-municipio`

### Parâmetros

| Parâmetro | Obrigatório | Exemplo | Descrição |
|-----------|:-----------:|---------|-----------|
| `mesAno` | ✅ | `202604` | Ano + mês no formato `AAAAMM` |
| `codigoIbge` | ✅ | `3550308` | Código IBGE do município (7 dígitos) |
| `pagina` | ❌ | `1` | Página da paginação (padrão `1`) |

### Exemplo de requisição

```bash
curl "https://api.portaldatransparencia.gov.br/api-de-dados/novo-bolsa-familia-por-municipio?mesAno=202604&codigoIbge=3550308&pagina=1" \
  -H "accept: */*" \
  -H "chave-api-dados: $PORTAL_TRANSPARENCIA_API_KEY"
```

### Exemplo de resposta (São Paulo-SP, abr/2026)

```json
[
  {
    "id": 101708076,
    "dataReferencia": "2026-04-01",
    "municipio": {
      "codigoIBGE": "3550308",
      "nomeIBGE": "SÃO PAULO",
      "codigoRegiao": "3",
      "nomeRegiao": "SUDESTE",
      "pais": "BRASIL",
      "uf": { "sigla": "SP", "nome": "SÃO PAULO" }
    },
    "tipo": {
      "id": 8,
      "descricao": "Novo Bolsa Família",
      "descricaoDetalhada": "Novo Bolsa Família"
    },
    "valor": 456815604.00,
    "quantidadeBeneficiados": 688825
  }
]
```

### Campos da resposta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | int | Identificador do registro |
| `dataReferencia` | date | Mês de referência (1º dia do mês) |
| `municipio.codigoIBGE` | string | Código IBGE |
| `municipio.nomeIBGE` | string | Nome do município |
| `municipio.uf` | object | UF (sigla + nome) |
| `municipio.nomeRegiao` | string | Região (ex.: SUDESTE) |
| `tipo.descricao` | string | Nome do programa |
| `valor` | decimal | Valor total pago no mês (R$) |
| `quantidadeBeneficiados` | int | Nº de famílias/pessoas beneficiadas |

---

## Outros endpoints úteis (a explorar)

A API cobre vários programas. Alguns endpoints relacionados a benefícios sociais:

| Endpoint | Descrição |
|----------|-----------|
| `/novo-bolsa-familia-sacado-por-nis` | Saques por NIS |
| `/auxilio-emergencial-por-municipio` | Auxílio Emergencial (histórico) |
| `/bpc-por-municipio` | Benefício de Prestação Continuada |
| `/safra-codigo-por-municipio` | Garantia-Safra |
| `/seguro-defeso-codigo` | Seguro Defeso |

> Consultar o Swagger para a lista completa e parâmetros de cada um.

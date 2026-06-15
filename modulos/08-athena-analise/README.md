# Módulo 08 — Athena (análise) — 🏆 Capstone

## 🎯 Objetivo
Responder a pergunta do projeto com SQL: **quais os 15 municípios que MAIS e que MENOS recebem** Bolsa Família.

## 🧠 Conceitos
- **Athena**: consulta SQL **serverless** direto sobre arquivos no S3 (usa o Glue Catalog como schema).
- **Você paga por dado escaneado** (~US$ 5/TB) — por isso Parquet + partição economizam muito.
- **JOIN fato × dimensão**: cruzar `bolsa_familia` com `dim_municipios` para trazer nome/UF/região.
- **Agregação**: `SUM`/`AVG` + `GROUP BY` para consolidar o ano; `ORDER BY ... LIMIT 15` para o ranking.

## ✅ Pré-requisitos
- Tabelas `bolsa_familia` e `dim_municipios` no Catalog (Módulo 07).

## 🪜 Passo a passo (console)
1. Athena → *Query editor*. Na 1ª vez, configure um **local de resultados** no S3
   (ex.: `s3://.../athena-results/`).
2. Selecione o database `transparencia`.
3. Abra [`sql/rankings.sql`](../../sql/rankings.sql) e rode as queries (troque `<DB>` por `transparencia`).
   - **Conferência** de linhas por mês;
   - **Top 15 que MAIS recebem** (valor anual);
   - **Top 15 que MENOS recebem** (valor anual, `> 0`);
   - **Per capita** (requer `dim_populacao`, ver abaixo).

### Exemplo (top 15 que mais recebem)
```sql
WITH fato_ano AS (
  SELECT codigo_ibge, SUM(valor) AS valor_ano
  FROM transparencia.bolsa_familia WHERE ano = 2024 GROUP BY codigo_ibge
)
SELECT d.municipio, d.uf_sigla, f.valor_ano
FROM fato_ano f
JOIN transparencia.dim_municipios d ON d.codigo_ibge = f.codigo_ibge
ORDER BY f.valor_ano DESC
LIMIT 15;
```

## ⭐ Bônus: ranking PER CAPITA
O ranking absoluto só mostra as maiores cidades. Para "onde o programa pesa mais por
habitante", precisamos da **população** por município (endpoint de estimativas do IBGE):
crie uma `dim_populacao(codigo_ibge, populacao)` e use a última query do `rankings.sql`.

## 🔍 Validação
- O top "mais" traz capitais/grandes cidades (SP, Rio, Fortaleza...).
- O top "menos" traz municípios pequenos (com `valor_ano > 0`).
- O painel do Athena mostra **quanto foi escaneado** (deve ser MBs, não GBs).

## 🏋️ Exercícios
1. Faça o ranking por **região** (`GROUP BY regiao_nome`).
2. Compare janeiro vs dezembro do mesmo ano.
3. Crie uma **view** com o ranking anual para reuso.

## 💲 Custos / Free Tier
- Athena cobra ~US$ 5/TB escaneado. Nossos dados (MBs) → **fração de centavo**. Parquet + partição mantêm isso mínimo.

## 🧹 Limpeza
- Esvazie `s3://.../athena-results/` de tempos em tempos (Módulo 09).

➡️ Próximo: [Módulo 09 — Monitoramento & limpeza](../09-monitoramento-limpeza/README.md)

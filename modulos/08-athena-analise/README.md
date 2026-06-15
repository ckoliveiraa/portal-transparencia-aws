# Módulo 08 — Athena (análise) — 🏆 Capstone

## 🎯 Objetivo
Responder a pergunta do projeto com SQL: **quais os 15 municípios que MAIS e que MENOS recebem** Bolsa Família.

## 🧠 Conceitos
- **Athena**: consulta SQL **serverless** direto sobre arquivos no S3 (usa o Glue Catalog como schema).
- **Você paga por dado escaneado** (~US$ 5/TB) — por isso Parquet + partição economizam muito.
- **JOIN fato × dimensão**: cruzar `bolsa_familia` com `dim_municipios` para trazer nome/UF/região.
- **Agregação**: `SUM`/`AVG` + `GROUP BY` para consolidar o ano; `ORDER BY ... LIMIT 15` para o ranking.

## ✅ Pré-requisitos
- CURATED em Parquet (Módulo 06) e a dim CSV no S3 (Módulo 02).
- Tabelas no Catalog — via **Crawler (Módulo 07)** **ou** criadas **na mão** no passo 2 abaixo
  (foi o que fizemos na prática).

## 🪜 Passo a passo (console)
1. Athena → *Query editor*. Na 1ª vez, configure o **local de resultados** no S3:
   `s3://transparencia-datalake-us-east-1-training/athena-results/`
   (*Settings → Manage → Query result location*).
2. **Catalogar na mão (DDL)** — alternativa ao Crawler; o aluno **vê o schema**. Rode no editor:
   ```sql
   CREATE DATABASE IF NOT EXISTS transparencia;

   -- fato: Parquet particionado
   CREATE EXTERNAL TABLE IF NOT EXISTS transparencia.bolsa_familia (
     id bigint, data_referencia date, codigo_ibge string, municipio string,
     uf_sigla string, regiao_nome string, programa string,
     valor double, qtd_beneficiados bigint
   ) PARTITIONED BY (ano int, mes int)
   STORED AS PARQUET
   LOCATION 's3://transparencia-datalake-us-east-1-training/curated/bolsa_familia/';

   -- descobre as partições ano=/mes= já existentes (sem isso, a tabela retorna 0 linhas)
   MSCK REPAIR TABLE transparencia.bolsa_familia;

   -- dimensão: CSV com cabeçalho
   CREATE EXTERNAL TABLE IF NOT EXISTS transparencia.dim_municipios (
     codigo_ibge string, municipio string, uf_sigla string, uf_nome string,
     uf_codigo string, regiao_sigla string, regiao_nome string,
     mesorregiao string, microrregiao string
   ) ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
   STORED AS TEXTFILE
   LOCATION 's3://transparencia-datalake-us-east-1-training/raw/dim_municipios/'
   TBLPROPERTIES ('skip.header.line.count'='1');
   ```
   > 💡 Rode o `MSCK REPAIR TABLE` de novo sempre que surgir um `ano/mes` novo no curated.
3. Selecione o database `transparencia` e abra [`sql/rankings.sql`](../../sql/rankings.sql)
   (troque `<DB>` por `transparencia`).
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

<details>
<summary>📄 <code>sql/rankings.sql</code> — todas as queries (clique para copiar)</summary>

```sql
-- =====================================================================
-- Athena — Módulo 08 — Análise: top 15 que MAIS e que MENOS recebem
-- =====================================================================
-- Pré-requisitos:
--   - Glue Catalog com as tabelas: bolsa_familia (curated) e dim_municipios
--   - Banco de dados (database) do Glue: ajuste o nome abaixo se necessário
--
-- Substitua <DB> pelo nome do seu database no Glue Catalog.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0) Conferência rápida: quantas linhas/partições temos?
-- ---------------------------------------------------------------------
SELECT ano, mes, COUNT(*) AS municipios, SUM(valor) AS valor_total
FROM <DB>.bolsa_familia
GROUP BY ano, mes
ORDER BY ano, mes;


-- ---------------------------------------------------------------------
-- 1) Agregação ANUAL por município (soma dos 12 meses) + enriquecimento
--    com a dimensão (UF, nome, região). Base para os rankings.
-- ---------------------------------------------------------------------
-- Parametrize o ano trocando 2024.
WITH fato_ano AS (
    SELECT
        codigo_ibge,
        SUM(valor)            AS valor_ano,
        SUM(qtd_beneficiados) AS beneficiados_ano,
        AVG(qtd_beneficiados) AS beneficiados_med_mes
    FROM <DB>.bolsa_familia
    WHERE ano = 2024
    GROUP BY codigo_ibge
),
base AS (
    SELECT
        d.codigo_ibge,
        d.municipio,
        d.uf_sigla,
        d.regiao_nome,
        f.valor_ano,
        f.beneficiados_ano
    FROM fato_ano f
    JOIN <DB>.dim_municipios d
      ON d.codigo_ibge = f.codigo_ibge
)
SELECT * FROM base;   -- (CTE de apoio; usada nas queries abaixo)


-- ---------------------------------------------------------------------
-- 2) TOP 15 que MAIS recebem (valor absoluto no ano)
-- ---------------------------------------------------------------------
WITH fato_ano AS (
    SELECT codigo_ibge, SUM(valor) AS valor_ano, SUM(qtd_beneficiados) AS beneficiados_ano
    FROM <DB>.bolsa_familia WHERE ano = 2024 GROUP BY codigo_ibge
)
SELECT
    d.municipio, d.uf_sigla, d.regiao_nome,
    f.valor_ano,
    f.beneficiados_ano
FROM fato_ano f
JOIN <DB>.dim_municipios d ON d.codigo_ibge = f.codigo_ibge
ORDER BY f.valor_ano DESC
LIMIT 15;


-- ---------------------------------------------------------------------
-- 3) TOP 15 que MENOS recebem (valor absoluto no ano)
--    Filtra valor_ano > 0 para ignorar municípios sem pagamento no ano.
-- ---------------------------------------------------------------------
WITH fato_ano AS (
    SELECT codigo_ibge, SUM(valor) AS valor_ano, SUM(qtd_beneficiados) AS beneficiados_ano
    FROM <DB>.bolsa_familia WHERE ano = 2024 GROUP BY codigo_ibge
)
SELECT
    d.municipio, d.uf_sigla, d.regiao_nome,
    f.valor_ano,
    f.beneficiados_ano
FROM fato_ano f
JOIN <DB>.dim_municipios d ON d.codigo_ibge = f.codigo_ibge
WHERE f.valor_ano > 0
ORDER BY f.valor_ano ASC
LIMIT 15;


-- ---------------------------------------------------------------------
-- 4) (Capstone PER CAPITA) — requer a tabela dim_populacao
--    (codigo_ibge, populacao) vinda do endpoint de estimativas do IBGE.
--    valor_per_capita = valor_ano / populacao
-- ---------------------------------------------------------------------
-- TOP 15 MAIS por habitante:
WITH fato_ano AS (
    SELECT codigo_ibge, SUM(valor) AS valor_ano
    FROM <DB>.bolsa_familia WHERE ano = 2024 GROUP BY codigo_ibge
)
SELECT
    d.municipio, d.uf_sigla,
    f.valor_ano,
    p.populacao,
    ROUND(f.valor_ano / p.populacao, 2) AS valor_per_capita
FROM fato_ano f
JOIN <DB>.dim_municipios d ON d.codigo_ibge = f.codigo_ibge
JOIN <DB>.dim_populacao  p ON p.codigo_ibge = f.codigo_ibge
WHERE p.populacao > 0
ORDER BY valor_per_capita DESC
LIMIT 15;
```

</details>

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

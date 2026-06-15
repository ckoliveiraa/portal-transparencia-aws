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
-- Parametrize o ano trocando 2026.
WITH fato_ano AS (
    SELECT
        codigo_ibge,
        SUM(valor)            AS valor_ano,
        SUM(qtd_beneficiados) AS beneficiados_ano,
        AVG(qtd_beneficiados) AS beneficiados_med_mes
    FROM <DB>.bolsa_familia
    WHERE ano = 2026
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
    FROM <DB>.bolsa_familia WHERE ano = 2026 GROUP BY codigo_ibge
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
    FROM <DB>.bolsa_familia WHERE ano = 2026 GROUP BY codigo_ibge
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
    FROM <DB>.bolsa_familia WHERE ano = 2026 GROUP BY codigo_ibge
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

# Módulo 02 — S3 e o Data Lake em camadas

## 🎯 Objetivo
Criar os buckets do data lake e subir os dados brutos (dim + fatos) com particionamento.

## 🧠 Conceitos
- **S3 (Simple Storage Service)**: armazenamento de objetos (arquivos) praticamente infinito.
- **Bucket**: "pasta raiz" com nome **único globalmente**.
- **Prefixo / "pasta"**: o S3 não tem pastas de verdade; usamos prefixos no nome da chave (`raw/...`).
- **Camadas (medallion)**: `raw` (bronze, dado cru) e `curated` (silver, dado tratado).
- **Particionamento**: organizar por `ano=/mes=/uf=` acelera e barateia consultas no Athena.

## ✅ Pré-requisitos
- Módulo 00 (conta/CLI) e Módulo 01 (dados locais em `data/`).

## 🪜 Passo a passo (console)
1. **Criar o bucket**: S3 → *Create bucket*.
   - Nome único, ex.: `transparencia-datalake-SEUNOME`.
   - Região: a mesma do curso (ex.: `us-east-1`).
   - **Block all public access**: deixe MARCADO (dados não devem ser públicos).
2. **Entender o layout de prefixos** que usaremos:
   ```
   s3://transparencia-datalake-SEUNOME/
   ├── raw/dim_municipios/dim_municipios.csv
   ├── raw/bolsa_familia/ano=2024/mes=01/uf=SP/municipio=3550308.json
   ├── curated/bolsa_familia/ano=2024/mes=01/part-*.parquet
   └── _checkpoints/202401.json
   ```
3. **Quem popula o bucket?** Nada de `aws s3 cp` — **tudo entra pela nuvem, via API**:
   - a **Lambda dim** (`handler_dim.py`) busca os municípios no IBGE e grava
     `raw/dim_municipios/dim_municipios.csv` (Módulo 04);
   - a **Lambda worker** (`handler.py`) busca os fatos e grava
     `raw/bolsa_familia/ano=/mes=/uf=/...json` (Módulos 04/05).

   Ou seja: neste módulo você só **cria o bucket e entende o layout**. Os dados chegam
   quando você rodar as Lambdas. (O coletor local do Módulo 01 é apenas para *entender*
   a API na sua máquina — não faz parte do fluxo da nuvem.)

## 🔍 Validação
- O bucket existe e está vazio:
  ```bash
  aws s3 ls s3://transparencia-datalake-SEUNOME/
  ```
- Depois do Módulo 04, este mesmo comando mostrará `raw/dim_municipios/` e `raw/bolsa_familia/`
  preenchidos — sem nenhum upload manual.

## 🏋️ Exercícios
1. Ative o **versionamento** do bucket e suba o mesmo arquivo duas vezes — veja as versões.
2. Crie um **lifecycle rule** que expira objetos em `_checkpoints/` após 30 dias.

## 💲 Custos / Free Tier
- Free Tier: **5 GB** de S3 grátis por 12 meses. Nossos dados são poucos MB → **centavos ou zero**.

## 🧹 Limpeza
- Para zerar: `aws s3 rm s3://transparencia-datalake-SEUNOME/ --recursive` (cuidado!). Removemos o bucket no Módulo 10.

➡️ Próximo: [Módulo 03 — Secrets Manager](../03-secrets-manager/README.md)

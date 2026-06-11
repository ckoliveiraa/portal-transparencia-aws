# Diagrama de arquitetura

Pipeline de dados serverless na AWS, no padrão **data lake em camadas (medallion)**.
O diagrama abaixo renderiza direto no GitHub (Mermaid). Versão em imagem: [`arquitetura.png`](arquitetura.png).

![Diagrama de arquitetura](arquitetura.png)

```mermaid
flowchart TB
    subgraph EXT["🌐 Fontes externas"]
        IBGE["IBGE API<br/>(municípios)"]
        PT["API Portal da Transparência<br/>Novo Bolsa Família<br/>1 req/município · 30 req/min"]
    end

    subgraph ING["⚙️ Ingestão — Lambda (serverless)"]
        LDIM["Lambda dim<br/>handler_dim.py"]
        LFATO["Lambda worker em LOTES<br/>handler.py<br/>checkpoint · idempotência · retry 429"]
        EB["EventBridge<br/>(re-invoca a cada ~15 min<br/>até fechar o mês)"]
        SM["Secrets Manager<br/>chave-api-dados"]
    end

    subgraph LAKE["🪣 Data Lake — Amazon S3"]
        RAWDIM["RAW / dim_municipios<br/>CSV · 5.571 linhas"]
        RAW["RAW / bolsa_familia<br/>bronze · JSON<br/>ano=/mes=/uf=/cod.json"]
        CHK["_checkpoints/<br/>AAAAMM.json"]
        CUR["CURATED / bolsa_familia<br/>silver · Parquet<br/>ano=/mes="]
    end

    subgraph TRANSF["🔥 Transformação & Catálogo — AWS Glue"]
        GJOB["Glue Job (PySpark)<br/>job_bolsa_familia.py<br/>limpa · achata · tipa · particiona"]
        CRAWL["Glue Crawler"]
        CAT["Glue Data Catalog<br/>(metastore / tabelas)"]
    end

    subgraph CONS["📊 Consulta"]
        ATH["Amazon Athena<br/>SQL serverless<br/>rankings.sql — top 15 +/-"]
    end

    subgraph CROSS["🛡️ Transversal"]
        IAM["IAM<br/>least privilege"]
        CW["CloudWatch<br/>logs & métricas"]
        TF["Terraform<br/>IaC — recria a stack"]
    end

    IBGE --> LDIM --> RAWDIM
    PT --> LFATO --> RAW
    EB --> LFATO
    SM -.chave.-> LFATO
    LFATO <-.offset.-> CHK
    RAWDIM --> GJOB
    RAW --> GJOB --> CUR
    CUR --> CRAWL --> CAT --> ATH

    CROSS -.governa todos os serviços.-> LAKE

    classDef ext fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef compute fill:#fff4e5,stroke:#ff9900,color:#111
    classDef storage fill:#e6f4ea,stroke:#34a853,color:#111
    classDef query fill:#f3e8fd,stroke:#a142f4,color:#111
    classDef cross fill:#fce8e6,stroke:#ea4335,color:#111

    class IBGE,PT ext
    class LDIM,LFATO,EB,SM,GJOB,CRAWL,CAT compute
    class RAWDIM,RAW,CHK,CUR storage
    class ATH query
    class IAM,CW,TF cross
```

## Como ler o fluxo

1. **Fontes externas** → duas APIs públicas: IBGE (dimensão de municípios) e Portal da
   Transparência (fatos do Bolsa Família, 1 requisição por município).
2. **Ingestão (Lambda)** → a `Lambda dim` carrega os 5.571 municípios; a `Lambda worker`
   coleta os fatos **em lotes**, lendo a chave do **Secrets Manager**, salvando
   **checkpoint** no S3 e sendo re-invocada pelo **EventBridge** até fechar o mês.
3. **Data Lake (S3)** → dados crus em **RAW (bronze, JSON)**; depois tratados em
   **CURATED (silver, Parquet)**, particionados por `ano/mes`.
4. **Transformação & Catálogo (Glue)** → o **Glue Job (PySpark)** limpa e converte para
   Parquet; o **Crawler** descobre o schema e popula o **Data Catalog**.
5. **Consulta (Athena)** → SQL serverless sobre o catálogo (ranking dos 15 municípios que
   mais/menos recebem).
6. **Transversal** → **IAM** (least privilege), **CloudWatch** (observabilidade) e
   **Terraform** (recria toda a stack como código) atravessam todos os serviços.

> Detalhes de camadas, glossário de serviços e trade-offs em [`arquitetura.md`](arquitetura.md).

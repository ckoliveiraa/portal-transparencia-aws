# Módulo 05 — Step Functions (orquestração)

## 🎯 Objetivo
Orquestrar a ingestão de ponta a ponta com uma **máquina de estados**: reinvocar a Lambda
worker em **lotes** até o mês fechar, disparar o **Glue** (transformação) e rodar o **Crawler**
(atualiza as partições no Data Catalog) — tudo num fluxo só, que **para sozinho**, sem agendador.

## 🧠 Conceitos
- **AWS Step Functions**: serviço de orquestração serverless; você descreve um fluxo como uma
  **máquina de estados** (state machine) em **ASL** (Amazon States Language, um JSON).
- **Task**: um estado que executa trabalho — aqui, `lambda:invoke` (o worker),
  `glue:startJobRun.sync` (o ETL) e chamadas de SDK ao Glue (o crawler).
- **`.sync`**: o Step Functions **espera** o Glue job terminar antes de seguir (integração síncrona).
- **Integração SDK + polling**: o **crawler** não tem `.sync`. Então fazemos `startCrawler`, e um
  laço `Wait → getCrawler → Choice(State == READY?)` espera ele terminar — o mesmo padrão de
  "polling" que você faria na mão.
- **Choice**: estado de decisão. Olhamos `concluido` no retorno do worker (loop dos lotes) e o
  `State` do crawler (espera). É isso que faz o fluxo **terminar sozinho**.
- **Por que ainda em lotes**: o Step Functions **não remove** o teto de 15 min da Lambda nem o
  rate limit. O worker continua processando ~400 municípios por invocação com **checkpoint +
  idempotência** (Módulo 04); o Step Functions só **repete** os lotes e sabe quando parar.

## ✅ Pré-requisitos
- Módulo 04 (Lambda worker funcionando e testada manualmente).
- Glue job `transparencia-glue-bolsa-familia` criado (Módulo 06).
- Glue crawler `transparencia-bolsa-familia-crawler` apontando para `curated/bolsa_familia/`
  (Módulo 07). Se ainda não tiver job/crawler, monte a máquina só com o loop de ingestão e
  adicione os passos do Glue/Crawler depois.

## 🧩 A máquina de estados (já pronta)
[`stepfunctions/ingestao_bolsa_familia.asl.json`](../../stepfunctions/ingestao_bolsa_familia.asl.json):

```
IngestarLote (invoke worker) ──> MesFechou? (Choice no concluido)
        ▲                               │ false
        └───────────────────────────────┘
                                        │ true
                                        ▼
                          TransformarGlue (startJobRun.sync)
                                        │
                                        ▼
              CatalogarCrawler (startCrawler) ──> AguardarCrawler (Wait 30s)
                                        ▲                    │
                                        │                    ▼
                          CrawlerPronto? <── EstadoCrawler (getCrawler)
                          │ READY
                          ▼
                     Concluido (Succeed)
```

<details>
<summary>📄 <code>stepfunctions/ingestao_bolsa_familia.asl.json</code> — ASL completo (clique para copiar)</summary>

```json
{
  "Comment": "Orquestra a ingestao do Bolsa Familia: repete a Lambda worker em lotes ate o mes fechar (checkpoint + idempotencia), dispara o Glue para gerar o curated e roda o Crawler para atualizar as particoes no Data Catalog. Para sozinho quando concluido=true.",
  "StartAt": "IngestarLote",
  "States": {
    "IngestarLote": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "transparencia-ingestao-worker",
        "Payload": {
          "ano.$": "$.ano",
          "mes.$": "$.mes"
        }
      },
      "ResultSelector": {
        "concluido.$": "$.Payload.concluido",
        "offset_final.$": "$.Payload.offset_final"
      },
      "ResultPath": "$.resultado",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.TooManyRequestsException", "Lambda.ServiceException", "States.TaskFailed"],
          "IntervalSeconds": 30,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Next": "MesFechou?"
    },
    "MesFechou?": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.resultado.concluido",
          "BooleanEquals": false,
          "Comment": "Ainda faltam municipios -> processa o proximo lote",
          "Next": "IngestarLote"
        }
      ],
      "Default": "TransformarGlue"
    },
    "TransformarGlue": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "transparencia-glue-bolsa-familia",
        "Arguments": {
          "--BUCKET": "transparencia-datalake-us-east-1-<projectname>"
        }
      },
      "Next": "CatalogarCrawler"
    },
    "CatalogarCrawler": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:glue:startCrawler",
      "Parameters": {
        "Name": "transparencia-bolsa-familia-crawler"
      },
      "Catch": [
        {
          "ErrorEquals": ["Glue.CrawlerRunningException"],
          "Comment": "Crawler ja rodando -> so aguarda terminar",
          "Next": "AguardarCrawler"
        }
      ],
      "Next": "AguardarCrawler"
    },
    "AguardarCrawler": {
      "Type": "Wait",
      "Seconds": 30,
      "Next": "EstadoCrawler"
    },
    "EstadoCrawler": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:glue:getCrawler",
      "Parameters": {
        "Name": "transparencia-bolsa-familia-crawler"
      },
      "ResultSelector": {
        "state.$": "$.Crawler.State"
      },
      "ResultPath": "$.crawler",
      "Next": "CrawlerPronto?"
    },
    "CrawlerPronto?": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.crawler.state",
          "StringEquals": "READY",
          "Comment": "Crawler terminou -> catalogo atualizado",
          "Next": "Concluido"
        }
      ],
      "Default": "AguardarCrawler"
    },
    "Concluido": {
      "Type": "Succeed"
    }
  }
}
```

</details>

## 🪜 Passo a passo (console)
1. **IAM Role da state machine** (`transparencia-sfn-role`), trust em `states.amazonaws.com`,
   com permissão para:
   - `lambda:InvokeFunction` no `transparencia-ingestao-worker`;
   - `glue:StartJobRun`, `glue:GetJobRun`, `glue:BatchStopJobRun` no job (o `.sync` precisa do
     `GetJobRun` para acompanhar);
   - `glue:StartCrawler`, `glue:GetCrawler` no crawler (`startCrawler` dispara, `getCrawler`
     é o polling do laço de espera).
2. **Criar a state machine**: Step Functions → *State machines* → *Create* → **Standard**
   (não Express — o fluxo dura horas).
3. 🖱️ Cole o ASL de `stepfunctions/ingestao_bolsa_familia.asl.json` (troque `<projectname>` no
   `--BUCKET`). Nome: `transparencia-ingestao`. Associe a role do passo 1.
4. **Executar**: *Start execution* com o input:
   ```json
   { "ano": 2026, "mes": 4 }
   ```
   - 👀 O gráfico mostra `IngestarLote` rodando em loop com `MesFechou?` até `concluido: true`,
     depois `TransformarGlue` (espera o Glue), o laço `CatalogarCrawler → AguardarCrawler →
     EstadoCrawler → CrawlerPronto?` e enfim `Concluido`.

> 🔑 **Sem agendador:** quem repete os lotes é o **Choice** da máquina, e a execução termina
> sozinha. Para uma cadência mensal automática, um agendador externo (cron) poderia só **iniciar**
> a execução (`StartExecution`) uma vez por mês — opcional e fora do fluxo base.

### Pela CLI (resumo)
```bash
# cria a state machine a partir do arquivo ASL
aws stepfunctions create-state-machine \
  --name transparencia-ingestao \
  --definition file://stepfunctions/ingestao_bolsa_familia.asl.json \
  --role-arn arn:aws:iam::<account>:role/transparencia-sfn-role \
  --type STANDARD

# dispara uma execução para abril/2026
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:<account>:stateMachine:transparencia-ingestao \
  --input '{"ano": 2026, "mes": 4}'
```

## 🔍 Validação
- A execução percorre `IngestarLote → MesFechou?` várias vezes (um lote por iteração) e
  **termina sozinha** em `Concluido` — sem nada rodando depois.
- O marcador aparece ao fim:
  ```bash
  aws s3 ls s3://transparencia-datalake-us-east-1-<projectname>/raw/bolsa_familia/ano=2026/mes=04/_SUCCESS
  ```
- O `TransformarGlue` só fica verde quando o Glue job conclui (graças ao `.sync`).
- O laço do crawler repete `AguardarCrawler → EstadoCrawler` até `State == READY`; aí o
  Data Catalog já tem as partições novas (sem `MSCK REPAIR` na mão).

## 💲 Custos / Free Tier
- Step Functions **Standard**: 4.000 transições/mês grátis; depois ~US$ 0,025/1.000. Nossas
  ~14 iterações × poucas transições → **frações de centavo**.
- O custo real do fluxo é o do **Glue** (não tem Free Tier) e da Lambda (coberta) — não do SFN.

## 🧹 Limpeza
- Não há agendador rodando para sempre: a execução termina sozinha. Para remover de vez:
  Step Functions → *Delete state machine* (Módulo 09).

➡️ Próximo: [Módulo 06 — Glue (transformação)](../06-glue-transformacao/README.md)

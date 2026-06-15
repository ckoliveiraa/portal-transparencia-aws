# Módulo 06 — Step Functions (orquestração)

## 🎯 Objetivo
Orquestrar a ingestão de ponta a ponta com uma **máquina de estados**: reinvocar a Lambda
worker em **lotes** até o mês fechar e, ao concluir, disparar o **Glue** — tudo num fluxo só,
que **para sozinho**, sem agendador. (O próprio Glue job cataloga as partições, então não há
passo de crawler — ver Módulo 05.)

## 🧠 Conceitos
- **AWS Step Functions**: serviço de orquestração serverless; você descreve um fluxo como uma
  **máquina de estados** (state machine) em **ASL** (Amazon States Language, um JSON).
- **Task**: um estado que executa trabalho — aqui, `lambda:invoke` (o worker) e
  `glue:startJobRun.sync` (o ETL).
- **`.sync`**: o Step Functions **espera** o Glue job terminar antes de seguir (integração síncrona).
- **Choice**: estado de decisão. Olhamos `concluido` no retorno do worker: se `false`, volta pro
  lote seguinte; se `true`, segue pro Glue. É isso que faz o fluxo **terminar sozinho**.
- **Por que ainda em lotes**: o Step Functions **não remove** o teto de 15 min da Lambda nem o
  rate limit. O worker continua processando ~400 municípios por invocação com **checkpoint +
  idempotência** (Módulo 04); o Step Functions só **repete** os lotes e sabe quando parar.

## ✅ Pré-requisitos
- Módulo 04 (Lambda worker funcionando e testada manualmente).
- Glue job `transparencia-glue-bolsa-familia` já criado (Módulo 05) — a state machine o dispara
  no passo `TransformarGlue`, então ele **precisa existir antes** deste módulo.

## 🧩 A máquina de estados (já pronta)
[`stepfunctions/ingestao_bolsa_familia.asl.json`](../../stepfunctions/ingestao_bolsa_familia.asl.json):

```
IngestarLote (invoke worker) ──> MesFechou? (Choice no concluido)
        ▲                               │ false
        └───────────────────────────────┘
                                        │ true
                                        ▼
                          TransformarGlue (startJobRun.sync) ──> Concluido (Succeed)
```

<details>
<summary>📄 <code>stepfunctions/ingestao_bolsa_familia.asl.json</code> — ASL completo (clique para copiar)</summary>

```json
{
  "Comment": "Orquestra a ingestao do Bolsa Familia: repete a Lambda worker em lotes ate o mes fechar (checkpoint + idempotencia) e, ao concluir, dispara o Glue. O proprio Glue job cataloga as particoes (ADD PARTITION), entao nao ha passo de crawler. Para sozinho quando concluido=true.",
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
      "Next": "Concluido"
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
     `GetJobRun` para acompanhar).
2. **Criar a state machine**: Step Functions → *State machines* → *Create* → **Standard**
   (não Express — o fluxo dura horas).
3. 🖱️ Cole o ASL de `stepfunctions/ingestao_bolsa_familia.asl.json` (troque `<projectname>` no
   `--BUCKET`). Nome: `transparencia-ingestao`. Associe a role do passo 1.
4. **Executar**: *Start execution* com o input:
   ```json
   { "ano": 2026, "mes": 4 }
   ```
   - 👀 O gráfico mostra `IngestarLote` rodando em loop com `MesFechou?` até `concluido: true`,
     depois `TransformarGlue` (espera o Glue) e `Concluido`.

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
- Ao terminar, o catálogo já tem as partições novas — o **próprio Glue job** as registra
  (`ADD PARTITION`), sem crawler nem `MSCK REPAIR` na mão.

## 💲 Custos / Free Tier
- Step Functions **Standard**: 4.000 transições/mês grátis; depois ~US$ 0,025/1.000. Nossas
  ~14 iterações × poucas transições → **frações de centavo**.
- O custo real do fluxo é o do **Glue** (não tem Free Tier) e da Lambda (coberta) — não do SFN.

## 🧹 Limpeza
- Não há agendador rodando para sempre: a execução termina sozinha. Para remover de vez:
  Step Functions → *Delete state machine* (Módulo 09).

➡️ Próximo: [Módulo 07 — Athena + Data Catalog](../07-athena-analise/README.md)

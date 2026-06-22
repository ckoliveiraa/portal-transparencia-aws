# Módulo 08 — 🎓 Desafio final: auto-check de novos meses

> **Formato diferente dos outros módulos.** Aqui não há passo a passo pronto: é um
> **desafio de implementação** para você fechar o curso. Damos o objetivo, a arquitetura
> sugerida, um esqueleto com `TODO`s e os critérios de aceite — **o código é por sua conta**.

## 🎯 Objetivo
Hoje o pipeline é disparado **na mão**: alguém roda `StartExecution` com `{ "ano": 2026, "mes": 4 }`.
Seu desafio é torná-lo **autônomo**: detectar **quando a API publica um mês novo** e disparar a
máquina de estados **sozinho** — sem processar o mesmo mês duas vezes e sem invocar à toa.

A regra de ouro: a API do Portal da Transparência **não avisa** quando um mês fica disponível
(não há webhook). Ela publica os dados de um mês com **alguns dias/semanas de atraso**. Então
você precisa **sondar** (poll) periodicamente e **reagir** quando o dado aparecer.

## 🧠 Conceitos novos
- **Polling vs. evento**: sem webhook, a estratégia é checar de tempos em tempos (cron) se há
  algo novo. O segredo é a checagem ser **barata** (1 request) e **idempotente**.
- **EventBridge Scheduler**: cron gerenciado. Aqui ele **não** invoca o worker (como na v1 do
  projeto, que rodava à toa) — ele só chama um **detector** leve, que decide se vale a pena
  iniciar o pipeline. Voltamos a usar um agendador, mas agora **inteligente**.
- **Detector (probe)**: uma chamada-sonda à API com um município-sentinela. Resposta não-vazia
  ⇒ o mês existe.
- **Gatilho condicional**: `states:StartExecution` só quando (a) o mês candidato existe na API
  **e** (b) ainda não foi processado **e** (c) não há execução em andamento.

## 🧩 Arquitetura sugerida

```
EventBridge Scheduler           Lambda "detector"                 Step Functions
 (cron, ex.: diário 09:00 ─────> 1. acha o último mês processado ──> StartExecution
  BRT)                            2. calcula o mês candidato (+1)     {ano, mes}   (só se houver
                                  3. sonda a API (1 município)                      mês novo!)
                                  4. já processado? em execução? ──┐
                                     se sim → não faz nada  <───────┘
```

Reaproveita **tudo** que você já construiu: a state machine `transparencia-ingestao`
(Módulo 07) faz o trabalho pesado. O detector só decide **se** e **quando** acioná-la.

## ✅ Pré-requisitos
- Módulos 04–07 concluídos (worker, Glue, Athena, state machine).
- A state machine `transparencia-ingestao` existente e testada (Módulo 07).

## 📋 Requisitos (o que entregar)
1. **Lambda `transparencia-detector-mes`** que, a cada invocação:
   - descobre o **último mês processado** (sugestão: listar os marcadores
     `raw/bolsa_familia/ano=*/mes=*/_SUCCESS` no S3 e pegar o maior; alternativa: um arquivo de
     estado `_state/ultimo_mes.json`);
   - calcula o **mês candidato** = último + 1 (cuidado com a virada de ano: dez → jan);
   - **sonda** a API para esse `mesAno` com um município-sentinela (ex.: São Paulo,
     `codigoIbge=3550308`, que sempre tem dados);
   - **decide**: se a sonda voltar **não-vazia** e o mês ainda não tiver `_SUCCESS` e não houver
     execução em andamento → `StartExecution` da state machine com `{ano, mes}`;
   - caso contrário, **não faz nada** e loga o motivo.
2. **EventBridge Scheduler `transparencia-detector-diario`** que invoca o detector numa cadência
   sua (diária é suficiente — o dado muda no máximo 1×/mês).
3. **IAM**: role do detector com o **mínimo** necessário (ver abaixo).
4. **Idempotência**: rodar o detector 10× no mesmo dia **não** pode gerar 10 execuções nem
   reprocessar um mês já fechado.

## 🧱 Esqueleto (preencha os `TODO`)
Crie `src/lambda/handler_detector.py`. O esqueleto abaixo é só o andaime — a lógica é sua:

```python
"""Detector de mês novo: sonda a API e dispara a state machine quando há dados novos."""
import os, json, boto3, requests

BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"
ENDPOINT = "/novo-bolsa-familia-por-municipio"
SENTINELA = "3550308"  # São Paulo: sempre tem dados quando o mês existe

s3   = boto3.client("s3")
sfn  = boto3.client("stepfunctions")
secrets = boto3.client("secretsmanager")

BUCKET   = os.environ["BUCKET"]
SM_ARN   = os.environ["STATE_MACHINE_ARN"]
SECRET_NAME = os.environ.get("SECRET_NAME", "portal-transparencia/chave-api-dados")


def ultimo_mes_processado() -> tuple[int, int]:
    """TODO: varrer os _SUCCESS em raw/bolsa_familia/ e retornar (ano, mes) do mais recente.
    Dica: s3.get_paginator('list_objects_v2') com Prefix='raw/bolsa_familia/' e Delimiter,
    ou liste as chaves '.../_SUCCESS' e parseie ano=/mes= do path."""
    raise NotImplementedError


def proximo_mes(ano: int, mes: int) -> tuple[int, int]:
    """TODO: (ano, mes) + 1 mês, virando o ano em dezembro."""
    raise NotImplementedError


def mes_existe_na_api(mes_ano: str) -> bool:
    """TODO: 1 GET com codigoIbge=SENTINELA; True se a resposta (lista) for não-vazia.
    Header chave-api-dados vem do Secrets Manager (reaproveite a lógica do worker)."""
    raise NotImplementedError


def ja_concluido(ano: int, mes: int) -> bool:
    """TODO: head_object no _SUCCESS daquele mês -> True se já existe."""
    raise NotImplementedError


def ha_execucao_rodando() -> bool:
    """TODO: sfn.list_executions(statusFilter='RUNNING') no SM_ARN -> True se houver alguma."""
    raise NotImplementedError


def handler(event, context):
    ano, mes = proximo_mes(*ultimo_mes_processado())
    mes_ano = f"{ano}{mes:02d}"

    # TODO: combine as guardas. Só dispara se: existe na API, não concluído, nada rodando.
    if ja_concluido(ano, mes) or ha_execucao_rodando():
        print(json.dumps({"acao": "skip", "motivo": "ja_processado_ou_em_execucao", "mes_ano": mes_ano}))
        return {"disparado": False}

    if not mes_existe_na_api(mes_ano):
        print(json.dumps({"acao": "skip", "motivo": "mes_ainda_nao_publicado", "mes_ano": mes_ano}))
        return {"disparado": False}

    sfn.start_execution(
        stateMachineArn=SM_ARN,
        name=f"auto-{mes_ano}",  # nome determinístico = StartExecution idempotente no mesmo mês
        input=json.dumps({"ano": ano, "mes": mes}),
    )
    print(json.dumps({"acao": "start", "mes_ano": mes_ano}))
    return {"disparado": True, "mes_ano": mes_ano}
```

> 💡 **Truque de idempotência:** em state machine **Standard**, dois `StartExecution` com o
> **mesmo `name`** dão `ExecutionAlreadyExists` (o segundo falha de propósito). Usar
> `name=f"auto-{mes_ano}"` já te protege de disparo duplicado no mesmo mês — trate essa exceção
> como "já disparei, tudo certo".

## 🔐 IAM (least privilege)
Role do detector (`transparencia-detector-role`) precisa só de:
- `s3:ListBucket` + `s3:GetObject` no bucket (achar `_SUCCESS`);
- `secretsmanager:GetSecretValue` no segredo da chave;
- `states:StartExecution` **na** `transparencia-ingestao` + `states:ListExecutions`;
- logs do CloudWatch.

E o **Scheduler** precisa de uma role com `lambda:InvokeFunction` no detector.

## 🪜 Roteiro sugerido
1. Escreva e teste o detector **localmente** (ou com um `mes` forçado pelo `event`) antes de subir.
2. Faça o deploy da Lambda (mesma receita do Módulo 04: zip + Layer `requests`, env
   `BUCKET`/`STATE_MACHINE_ARN`/`SECRET_NAME`).
3. Crie o **EventBridge Scheduler** apontando para o detector (cron diário; fuso à sua escolha).
4. Force um cenário de teste (veja abaixo) e observe a execução nascer sozinha.

## 🔍 Critérios de aceite
- [ ] Com o último mês **já publicado** na API e **sem** `_SUCCESS`, o detector dispara **uma**
      execução e o pipeline roda ponta a ponta.
- [ ] Rodando o detector **de novo** no mesmo mês: **não** cria execução nova (idempotente).
- [ ] Com o mês candidato **ainda não publicado**, o detector loga `mes_ainda_nao_publicado` e
      **não** dispara.
- [ ] A role do detector **não** tem `*` em recursos — só o que está na seção IAM.
- [ ] Teste da virada de ano: `ultimo = 2026-12` ⇒ candidato `2027-01`.

> **Como simular "mês novo" sem esperar a API:** apague (ou renomeie) o `_SUCCESS` e o
> `_checkpoints/AAAAMM.json` de um mês que você sabe que existe (ex.: `202604`) e rode o detector
> — ele deve tratar abril como "candidato disponível" e disparar. Restaure depois.

## ⭐ Extensões (se quiser ir além)
- **Notificação**: publique num tópico **SNS** ("mês 202605 detectado e em processamento") e
  receba e-mail.
- **Backfill**: e se faltarem **vários** meses? Faça o detector enfileirar do mais antigo ao mais
  novo (1 execução por mês, em ordem).
- **Tolerância a publicação parcial**: a API pode liberar um mês para algumas UFs antes de outras.
  Sonde 2–3 sentinelas de regiões diferentes e só dispare se todas responderem.
- **Trocar polling por evento real**: dispare o detector a partir do **`_SUCCESS`** do mês
  anterior (S3 Event/EventBridge) em vez de cron — discuta o trade-off.

## 💲 Custos / Free Tier
- EventBridge Scheduler: 14M invocações/mês grátis. 1 sonda/dia → **zero**.
- Lambda detector: milissegundos, 1 request → **dentro do Free Tier**.
- O custo real continua sendo o do **Glue**, e só quando há mês novo de verdade.

## 🧹 Limpeza
- Desabilite/exclua o **Scheduler** (`transparencia-detector-diario`) — senão ele sonda a API
  todo dia para sempre.
- Remova a Lambda detector e a role no teardown (Módulo 09).

➡️ Próximo: [Módulo 09 — Monitoramento & limpeza](../09-monitoramento-limpeza/README.md)
⬅️ Voltar ao [índice do curso](../../README.md)

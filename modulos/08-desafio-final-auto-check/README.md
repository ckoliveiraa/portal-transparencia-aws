# Módulo 08 — 🎓 Desafio final: auto-check de novos meses

> **Formato diferente dos outros módulos.** Aqui não há passo a passo pronto nem código de
> partida: é um **desafio de implementação** para você fechar o curso. Damos o objetivo, a
> arquitetura sugerida, os requisitos e os critérios de aceite — **a Lambda, a role/policy e o
> agendador são por sua conta**.

## 🎫 Card do desafio (estilo Jira)

> Trate este desafio como um ticket que caiu no seu board. Leia, estime e implemente.

| | |
|---|---|
| **Tipo** | 🟢 Story |
| **Chave** | `DATA-108` |
| **Título** | Disparar o pipeline de ingestão automaticamente quando a API publica um mês novo |
| **Épico** | Automação do pipeline de transparência |
| **Prioridade** | 🔼 High |
| **Story points** | 5 |
| **Sprint** | Sprint final do curso |
| **Responsável** | _você_ |
| **Labels** | `lambda` · `iam` · `eventbridge` · `step-functions` · `idempotência` |

**Descrição**
> Como time de dados, queremos que o pipeline de Bolsa Família rode **sozinho** assim que um novo
> mês fica disponível na API do Portal da Transparência, **sem** ninguém precisar disparar o
> `StartExecution` na mão e **sem** reprocessar meses já fechados.

**Contexto técnico**
- A API **não tem webhook** — é preciso **sondar** (poll) e reagir quando o dado aparecer.
- Já existe a state machine `transparencia-ingestao` (Módulo 07) que faz todo o trabalho pesado.
- Este ticket entrega só o **gatilho inteligente**, não mexe no pipeline existente.

**Tarefas (subtasks)**
- [ ] `DATA-108a` — Criar a **Lambda detector** que decide se há mês novo e dispara a state machine.
- [ ] `DATA-108b` — Sondar a API com um **município de referência** (escolher cidade + `codigoIbge`).
- [ ] `DATA-108c` — Criar **role + policy IAM** da Lambda com permissões mínimas (sem `*`).
- [ ] `DATA-108d` — Criar o **EventBridge Scheduler** (cron diário) + role para invocar a Lambda.
- [ ] `DATA-108e` — Garantir **idempotência** (rodar N× no dia ⇒ no máximo 1 execução por mês).

**Critérios de aceite (Definition of Done)** → ver seção [🔍 Critérios de aceite](#-critérios-de-aceite) abaixo.

**Fora de escopo**
- Alterar a state machine ou o worker existentes.
- Notificações, backfill de vários meses e troca de polling por evento → ver [⭐ Extensões](#-extensões-se-quiser-ir-além).

---

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
Este é o seu desafio de implementação — **a partir daqui o código é todo seu**. O que precisa existir
ao final:

1. **Uma Lambda detector** (`transparencia-detector-mes`) que, a cada invocação, decide sozinha se
   há um mês novo para processar e, em caso afirmativo, dispara a state machine
   `transparencia-ingestao` com `{ano, mes}`. Pense em como ela vai:
   - descobrir **qual foi o último mês já processado**;
   - calcular **qual seria o próximo mês candidato** (atenção à virada de ano: dez → jan);
   - **sondar a API** para checar se esse mês já está publicado, usando **um município de
     referência** que você sabe que sempre tem dados quando o mês existe (escolha qual e descubra
     o `codigoIbge` dele);
   - só então **disparar** — ou **não fazer nada** e registrar o motivo no log.
2. **Uma role + uma policy IAM** para essa Lambda, com o **mínimo de permissões** necessário para
   ela fazer o trabalho acima (pense: o que ela lê? o que ela chama? onde ela loga?). Nada de `*`
   em recursos.
3. **Um agendador** (EventBridge Scheduler) que invoque o detector periodicamente — diário é o
   suficiente, já que o dado muda no máximo 1×/mês — com a role que esse agendador precisa para
   invocar a Lambda.
4. **Idempotência**: rodar o detector 10× no mesmo dia **não** pode gerar 10 execuções nem
   reprocessar um mês já fechado. Descubra como garantir isso.

> 💡 **Dica de idempotência (sem entregar a solução):** em state machine **Standard**, dois
> `StartExecution` com o **mesmo `name`** falham no segundo (`ExecutionAlreadyExists`). Há aí uma
> forma elegante de se proteger de disparo duplicado no mesmo mês — pense em como usar isso a seu favor.

## 🧰 Pistas (sem código)
- **Último mês processado:** você já grava um marcador `_SUCCESS` em `raw/bolsa_familia/ano=*/mes=*/`
  a cada mês concluído. Dá para descobrir o último a partir disso (ou manter um arquivo de estado próprio).
- **Sondar a API:** 1 único `GET` no endpoint por município, com o `codigoIbge` da sua cidade de
  referência. Resposta não-vazia ⇒ o mês existe. A chave da API você já lê do Secrets Manager no worker
  (Módulo 04) — reaproveite essa lógica.
- **Não disparar à toa:** antes de chamar `StartExecution`, vale checar se o mês já tem `_SUCCESS` e
  se já não há uma execução em andamento na state machine.

## 🪜 Roteiro sugerido
1. Escreva e teste a lógica do detector **localmente** (ou com um `mes` forçado pelo `event`) antes de subir.
2. Crie a **role + policy** da Lambda (least privilege) e faça o deploy do detector (mesma receita do
   Módulo 04: zip + Layer `requests`, variáveis de ambiente que você precisar).
3. Crie o **EventBridge Scheduler** apontando para o detector (cron diário; fuso à sua escolha) com a
   role que ele precisa para invocar a Lambda.
4. Force um cenário de teste (veja abaixo) e observe a execução nascer sozinha.

## 🔍 Critérios de aceite
- [ ] Com o último mês **já publicado** na API e **sem** `_SUCCESS`, o detector dispara **uma**
      execução e o pipeline roda ponta a ponta.
- [ ] Rodando o detector **de novo** no mesmo mês: **não** cria execução nova (idempotente).
- [ ] Com o mês candidato **ainda não publicado**, o detector loga `mes_ainda_nao_publicado` e
      **não** dispara.
- [ ] A role do detector **não** tem `*` em recursos — só as permissões mínimas que ela usa de fato.
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

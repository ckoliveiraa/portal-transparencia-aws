# Módulo 05 — EventBridge (agendamento)

## 🎯 Objetivo
Automatizar a ingestão: re-invocar a Lambda periodicamente até o mês fechar (todos os 5.571).

## 🧠 Conceitos
- **EventBridge Scheduler**: agendador da AWS (cron/rate) que dispara alvos (ex.: Lambda).
- **Event-driven**: em vez de você rodar na mão, um evento (horário) aciona o processamento.
- **Idempotência + checkpoint** (do Módulo 04) é o que torna seguro disparar de novo: cada execução retoma e não duplica.

## ✅ Pré-requisitos
- Módulo 04 (Lambda funcionando e testada manualmente).

## 🪜 Passo a passo (console)
1. EventBridge → *Scheduler* → *Create schedule*.
2. **Recorrência**: *Rate-based* a cada **15 minutos** (cobre ~400 municípios por execução).
   > A 30 req/min, um mês inteiro leva ~14 execuções ≈ 3,5h de relógio.
3. **Target**: a Lambda do Módulo 04.
4. **Payload (input)** fixo:
   ```json
   { "ano": 2024, "mes": 1 }
   ```
5. Salve. A partir daí, a cada 15 min a Lambda avança um lote.

### Quando parar
Quando a Lambda gravar `_SUCCESS` (mês completo), as próximas execuções só verão
`pulados` (idempotência) — barato, mas inútil. Opções:
- **desabilitar** o schedule manualmente após o `_SUCCESS`; ou
- (avançado, fase 2) usar **Step Functions** para orquestrar e parar sozinho.

## 🔍 Validação
- Acompanhe o checkpoint subir a cada 15 min:
  ```bash
  aws s3 cp s3://.../_checkpoints/202401.json -
  ```
- Ao final, confirme o marcador:
  ```bash
  aws s3 ls s3://.../raw/bolsa_familia/ano=2024/mes=01/_SUCCESS
  ```

## 🏋️ Exercícios
1. Mude para *Cron-based* e dispare só às 2h da manhã.
2. Coletar outro mês: troque o payload para `{ "ano": 2024, "mes": 2 }`.

## 💲 Custos / Free Tier
- EventBridge Scheduler: **14M invocações/mês grátis**. Nosso uso → **zero**.

## 🧹 Limpeza
- **Importante**: desabilite/exclua o schedule para a Lambda não rodar para sempre. Detalhe no Módulo 10.

➡️ Próximo: [Módulo 06 — Glue (transformação)](../06-glue-transformacao/README.md)

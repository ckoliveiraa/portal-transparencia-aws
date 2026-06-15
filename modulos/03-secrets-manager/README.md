# Módulo 03 — Secrets Manager (guardando a chave)

## 🎯 Objetivo
Tirar a chave da API do `.env` e guardá-la com segurança na nuvem, para a Lambda usar.

## 🧠 Conceitos
- **Por que não hardcodar**: chave no código vaza no Git, em logs, em prints. Segredo fica em um cofre.
- **Secrets Manager**: serviço da AWS que guarda segredos criptografados e controla acesso via IAM.
- **Alternativa**: SSM Parameter Store (`SecureString`) — mais barato; usamos Secrets Manager por ser o padrão didático.

## ✅ Pré-requisitos
- Sua chave da API (Módulo 01).

## 🪜 Passo a passo (console)
1. Secrets Manager → *Store a new secret*.
2. Tipo: **Other type of secret**.
3. Em *Key/value*, adicione:
   - chave: `chave-api-dados`
   - valor: *(sua chave)*
   > Ou escolha *Plaintext* e cole só a string — o `handler.py` aceita os dois formatos.
4. Nome do segredo: `portal-transparencia/chave-api-dados`.
5. Finalize (sem rotação automática por enquanto).

## 🔍 Validação
```bash
aws secretsmanager get-secret-value \
  --secret-id portal-transparencia/chave-api-dados \
  --query SecretString --output text
```
Deve retornar sua chave (ou o JSON com ela).

## 🧩 Como a Lambda lê (já implementado)
Veja `src/lambda/handler.py` → função `get_chave()`:
```python
resp = secrets.get_secret_value(SecretId=SECRET_NAME)
# aceita string pura OU {"chave-api-dados": "..."}
```
A Lambda precisará da permissão IAM `secretsmanager:GetSecretValue` nesse segredo (Módulo 04).

## 💲 Custos / Free Tier
- Secrets Manager **não tem Free Tier**: ~**US$ 0,40/segredo/mês** + frações de centavo por 10k chamadas. Insignificante, mas existe — por isso o Módulo 09 remove o segredo.

## 🧹 Limpeza
```bash
aws secretsmanager delete-secret --secret-id portal-transparencia/chave-api-dados \
  --force-delete-without-recovery
```

➡️ Próximo: [Módulo 04 — Lambda (worker em lotes)](../04-lambda-ingestao/README.md)

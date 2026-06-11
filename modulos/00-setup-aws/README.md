# Módulo 00 — Setup da conta AWS

## 🎯 Objetivo
Preparar uma conta AWS segura e pronta para o curso, sem sustos na fatura.

## 🧠 Conceitos
- **Conta root vs usuário IAM**: a conta root (e-mail de cadastro) é todo-poderosa; no dia a dia usamos um **usuário IAM** com permissões limitadas.
- **MFA** (autenticação em 2 fatores): protege contra acesso indevido.
- **Free Tier**: faixa gratuita da AWS (válida por 12 meses + serviços "always free").
- **Região**: data center geográfico. Usaremos **us-east-1** (mais barata e com tudo disponível) ou **sa-east-1** (São Paulo).

## ✅ Pré-requisitos
- E-mail e cartão de crédito (a AWS exige, mas o Free Tier evita cobranças).

## 🪜 Passo a passo (console)
1. **Criar a conta** em https://aws.amazon.com → *Create an AWS Account*.
2. **Ativar MFA na conta root**: IAM → *Security credentials* → *Assign MFA* (use um app como Authy/Google Authenticator).
3. **Criar um usuário IAM** para você:
   - IAM → *Users* → *Create user* → marque *Provide user access to the console*.
   - Permissões: anexe `AdministratorAccess` (curso/sandbox; em produção seria mais restrito).
   - Ative MFA também nesse usuário.
4. **Alarme de billing (essencial!)**:
   - *Billing* → *Billing preferences* → ative *Receive Billing Alerts*.
   - CloudWatch (região us-east-1) → *Alarms* → *Create alarm* → métrica `EstimatedCharges` → limite ex.: **US$ 5** → notifica seu e-mail (SNS).
5. **Instalar e configurar o AWS CLI**:
   ```bash
   aws --version
   aws configure        # informe Access Key, Secret, região (us-east-1), output json
   aws sts get-caller-identity   # confirma que está autenticado
   ```
   > Gere a Access Key em IAM → seu usuário → *Security credentials* → *Create access key*.

## 🔍 Validação
- `aws sts get-caller-identity` retorna seu `Account` e `Arn`.
- Você consegue logar no console com o **usuário IAM** (não o root) e o MFA pede o código.
- O alarme de billing aparece em CloudWatch → Alarms.

## 🏋️ Exercícios
1. Crie um segundo alarme em US$ 1 só para treinar.
2. Liste seus usuários: `aws iam list-users`.

## 💲 Custos / Free Tier
- Tudo neste módulo é **gratuito**. O alarme de billing é a sua rede de segurança para o resto do curso.

## 🧹 Limpeza
- Nada a remover. **Guarde bem** a Access Key (e nunca a comite no Git).

➡️ Próximo: [Módulo 01 — A API e a chave](../01-api-ingestao-local/README.md)

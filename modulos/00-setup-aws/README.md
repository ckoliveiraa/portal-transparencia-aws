# Módulo 00 — Setup da conta AWS

## 🎯 Objetivo
Preparar uma conta AWS segura e pronta para o curso, sem sustos na fatura.

## 🧠 Conceitos
- **Conta root vs usuário IAM**: a conta root (e-mail de cadastro) é todo-poderosa; no dia a dia usamos um **usuário IAM** com permissões limitadas.
- **MFA** (autenticação em 2 fatores): protege contra acesso indevido.
- **Free Tier**: faixa gratuita da AWS (válida por 12 meses + serviços "always free").
- **Região**: data center geográfico. Usaremos **us-east-1 (N. Virginia)** no curso inteiro.
  ⚠️ O alarme de billing (`EstimatedCharges`) **só existe em us-east-1** — por isso fixamos ela.

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
   - 📥 **Download/instalação (oficial):** https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
     (Windows: instalador `.msi` em https://awscli.amazonaws.com/AWSCLIV2.msi)
   ```bash
   aws --version
   aws configure        # informe Access Key, Secret, região (us-east-1), output json
   aws sts get-caller-identity   # confirma que está autenticado
   ```

### Configurando o CLI pelo terminal (passo a passo)
O **usuário** e a **Access Key** você cria pelo console (passo 3); aqui só **conectamos** o CLI
local a essas credenciais.

1. No console: IAM → seu usuário → *Security credentials* → *Create access key* (tipo
   *Command Line Interface*). Anote o **Access Key ID** e o **Secret** — o Secret só aparece **uma vez**.
2. No terminal, rode `aws configure` e responda os 4 prompts:
   ```text
   AWS Access Key ID [None]:     AKIA....................   (o Access Key ID do passo 1)
   AWS Secret Access Key [None]: wJalr.................     (o Secret do passo 1)
   Default region name [None]:   us-east-1
   Default output format [None]: json
   ```
   Isso grava `~/.aws/credentials` (chaves) e `~/.aws/config` (região/output).
3. Confirme:
   ```bash
   aws sts get-caller-identity     # mostra Account e Arn do seu usuário
   aws configure list              # mostra o profile/região ativos
   ```
> 💡 Para separar contas/perfis, use `aws configure --profile <nome>` e depois `--profile <nome>`
> nos comandos (ou `setx AWS_PROFILE <nome>` no Windows / `export AWS_PROFILE=<nome>` no Linux/macOS).

## 🔍 Validação
- `aws sts get-caller-identity` retorna seu `Account` e `Arn`.
- Você consegue logar no console com o **usuário IAM** (não o root) e o MFA pede o código.
- O alarme de billing aparece em CloudWatch → Alarms.

## 💲 Custos / Free Tier
- Tudo neste módulo é **gratuito**. O alarme de billing é a sua rede de segurança para o resto do curso.

## 🧹 Limpeza
- Nada a remover. **Guarde bem** a Access Key (e nunca a comite no Git).

➡️ Próximo: [Módulo 01 — A API e a chave](../01-api-ingestao-local/README.md)

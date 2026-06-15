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
   > Gere a Access Key em IAM → seu usuário → *Security credentials* → *Create access key*.

## 🖥️ Variante: criar o usuário admin pelo terminal (AWS CLI)

Em vez dos passos 3 e 5 pelo console, dá para criar o usuário admin **direto na CLI**.
Como `aws iam ...` já precisa de uma credencial, primeiro você faz um **bootstrap** com uma
chave inicial e depois cria o usuário definitivo.

**1) Bootstrap — configure uma credencial inicial.**
Use a Access Key da conta **root** (IAM/console → *Security credentials* da root → *Create access key*).
```bash
aws configure
# AWS Access Key ID     : <chave do bootstrap>
# AWS Secret Access Key : <secret do bootstrap>
# Default region name   : us-east-1
# Default output format : json
aws sts get-caller-identity     # confirma quem você é
```
> ⚠️ Chave de **root** é poderosíssima — use só para este bootstrap e **apague-a** logo depois
> (passo 4). O ideal é nunca deixar Access Key ativa na root.

**2) Crie o usuário admin e dê permissão.**
```bash
aws iam create-user --user-name admin

aws iam attach-user-policy \
  --user-name admin \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

**3) Gere a Access Key / Secret do `admin` e configure a CLI com elas.**
```bash
# guarda a saída: o Secret só aparece UMA vez!
aws iam create-access-key --user-name admin
# {
#   "AccessKey": {
#     "AccessKeyId":     "AKIA...",
#     "SecretAccessKey": "wJalr...",
#     ...
#   }
# }

# passe essas duas chaves para um profile dedicado (não sobrescreve o bootstrap):
aws configure --profile admin
# AWS Access Key ID     : AKIA...        (AccessKeyId acima)
# AWS Secret Access Key : wJalr...        (SecretAccessKey acima)
# Default region name   : us-east-1
# Default output format : json

# confirme que agora você é o usuário admin:
aws sts get-caller-identity --profile admin
# "Arn": "arn:aws:iam::<conta>:user/admin"
```
> 💡 Use `--profile admin` nos comandos, ou defina `export AWS_PROFILE=admin` (Linux/macOS) /
> `setx AWS_PROFILE admin` (Windows) para virar o padrão da sessão.

**4) (Opcional) acesso ao console + MFA para o `admin`.**
```bash
# senha de console (troca obrigatória no 1º login)
aws iam create-login-profile --user-name admin \
  --password 'TroqueEstaSenha!123' --password-reset-required

# MFA virtual: cria, mostra o segredo p/ o app autenticador e ativa com 2 códigos seguidos
aws iam create-virtual-mfa-device --virtual-mfa-device-name admin-mfa \
  --outfile /tmp/mfa-qr.png --bootstrap-method QRCodePNG
aws iam enable-mfa-device --user-name admin \
  --serial-number arn:aws:iam::<conta>:mfa/admin-mfa \
  --authentication-code1 <código1> --authentication-code2 <código2>
```

**5) Remova a credencial de bootstrap (root).**
```bash
# liste e apague a Access Key da root usada no passo 1
aws iam list-access-keys                      # (ainda no profile bootstrap)
aws iam delete-access-key --access-key-id <AccessKeyId-do-bootstrap>
```
Depois disso, a CLI deve operar **só** com o profile `admin`.

## 🔍 Validação
- `aws sts get-caller-identity` retorna seu `Account` e `Arn`.
- Você consegue logar no console com o **usuário IAM** (não o root) e o MFA pede o código.
- O alarme de billing aparece em CloudWatch → Alarms.

## 💲 Custos / Free Tier
- Tudo neste módulo é **gratuito**. O alarme de billing é a sua rede de segurança para o resto do curso.

## 🧹 Limpeza
- Nada a remover. **Guarde bem** a Access Key (e nunca a comite no Git).

➡️ Próximo: [Módulo 01 — A API e a chave](../01-api-ingestao-local/README.md)

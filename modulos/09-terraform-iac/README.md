# Módulo 09 — Terraform (Infraestrutura como Código)

## 🎯 Objetivo
Recriar **toda a stack** que você montou no console, agora como **código reprodutível**.

## 🧠 Conceitos
- **IaC (Infrastructure as Code)**: descrever a infra em arquivos versionáveis em vez de cliques.
- **Terraform**: ferramenta IaC multi-nuvem (padrão de mercado).
- **`terraform plan`/`apply`/`destroy`**: prever, aplicar e destruir a infra.
- **State**: o Terraform guarda o estado atual da infra (`terraform.tfstate`) para saber o que mudar.
- **Idempotência da infra**: aplicar duas vezes não duplica recursos.

## ✅ Pré-requisitos
- Ter feito os módulos no console (para entender o que o código representa).
- Terraform instalado (`terraform -version`) e AWS CLI configurada.

## 🧩 O código (esqueleto pronto)
Pasta [`terraform/`](../../terraform/):
- `variables.tf` — bucket, região, nome do segredo, etc.
- `main.tf` — S3, IAM roles, Secrets Manager, Lambda, Layer, EventBridge, Glue (database/job/crawler).
- `outputs.tf` — nomes/ARNs criados.

## 🪜 Passo a passo
```bash
cd terraform
terraform init                 # baixa o provider AWS
terraform plan -out tf.plan    # mostra o que será criado (revise!)
terraform apply tf.plan        # cria a infra
```
> Comece destruindo o que criou no console para evitar conflito de nomes (ou use nomes novos).

## 🔍 Validação
- `terraform apply` termina sem erro e os `outputs` aparecem.
- Os recursos existem no console (bucket, função, schedule, database Glue).
- `terraform plan` de novo mostra **"No changes"** (estado convergido).

## 🏋️ Exercícios
1. Mude o `rate` do EventBridge via variável e rode `apply` — veja só o que muda no `plan`.
2. Adicione `versioning` ao bucket pelo Terraform.
3. (Avançado) Mova o state para um **backend S3** remoto.

## 💲 Custos / Free Tier
- O Terraform é **gratuito**. O custo é o dos recursos criados (os mesmos dos módulos anteriores).

## 🧹 Limpeza
```bash
terraform destroy        # remove TUDO que o Terraform criou
```
Esse é o jeito mais limpo de zerar o projeto (complementado pelo Módulo 10).

➡️ Próximo: [Módulo 10 — Monitoramento & limpeza](../10-monitoramento-limpeza/README.md)

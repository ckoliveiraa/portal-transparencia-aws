# Guia passo a passo (pela UI) — roteiro mão na massa 🖱️

> **O que é este documento:** o **roteiro linear** que seguimos na prática, na ordem
> exata dos cliques no **console AWS** e nos portais web. Diferente dos READMEs dos
> módulos (que são didáticos), aqui o foco é **fazer**: cada passo é uma ação na tela,
> pensado para você **treinar antes de gravar o vídeo** e para o aluno acompanhar
> de forma interativa.
>
> 📌 Convenções:
> - 🖱️ = ação de clique/navegação na UI · ⌨️ = algo digitado · 👀 = o que você deve ver na tela
> - 💲 = aviso de custo · ⚠️ = atenção/erro comum · 🎬 = dica de narração para a gravação

## Progresso

| # | Passo | Onde | Status |
|---|-------|------|:------:|
| 1 | Criar conta gov.br e obter a chave da API | portal web | ✅ documentado |
| 2 | Apresentar a API (Swagger + 1ª chamada) | navegador | ✅ documentado |
| 3 | Conseguir a tabela de municípios (IBGE) — a dimensão | navegador + terminal | ✅ documentado |
| 4 | Baixar os fatos do Bolsa Família (1ª coleta local) | terminal local | ✅ documentado |
| 5 | Blindar a conta AWS: MFA, usuário IAM, **alarme de billing**, CLI | console AWS | ✅ documentado |
| 6 | Criar o bucket S3 (data lake) e entender o layout | console AWS | ✅ documentado |
| 7 | Guardar a chave da API no Secrets Manager | console AWS | ✅ documentado |
| 8 | Subir as Lambdas (dim + worker): Layer, role, env, teste | console AWS | ✅ documentado |
| 9 | EventBridge: reinvocar a Lambda até fechar o mês | console AWS | ✅ documentado |
| 10 | Glue (PySpark): raw JSON → curated Parquet | console AWS | ✅ documentado |
| 11 | Athena: catalogar tabelas e rodar o capstone SQL | console AWS | ✅ documentado |
| 12 | Monitoramento & teardown | console AWS | ⏳ a fazer |

---

## Passo 1 — Criar conta gov.br e obter a chave da API 🔑

**Objetivo:** ter em mãos a `chave-api-dados` (gratuita, sai na hora) que autentica
todas as chamadas. Sem ela, a API responde `401`.

🎬 *Narração:* "Antes de tocar na AWS, a gente precisa da matéria-prima: os dados.
Eles vêm da API do Portal da Transparência, e o primeiro passo é pegar nossa chave de acesso."

1. 🖱️ Abra a página de cadastro da chave:
   👉 https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email
2. 🖱️ Clique em **entrar com gov.br** e faça login.
   - 👀 Se não tiver conta, o próprio fluxo leva a https://acesso.gov.br — crie com **CPF**;
     o nível **bronze** já é suficiente.
3. ⌨️ Informe o **e-mail** onde quer receber a chave e confirme.
4. 👀 O Portal gera o **token** (a `chave-api-dados`) vinculado à sua conta — uma string
   longa, ex.: `0c2edd2dce68b77258f713fb2130b602`. Copie.
5. ⌨️ Guarde no arquivo `.env` na raiz do projeto:
   ```env
   PORTAL_TRANSPARENCIA_API_KEY=sua_chave_aqui
   ```
   > ⚠️ O `.env` está no `.gitignore` — a chave **nunca** vai para o Git. No Passo (módulo 03)
   > ela migra para o **AWS Secrets Manager**.

💲 **Custo:** zero. A chave e a API são gratuitas.

---

## Passo 2 — Apresentar a API (Swagger + primeira chamada) 📚

**Objetivo:** mostrar ao aluno *o que* a API entrega, *como* se chama e *o que* volta,
antes de automatizar qualquer coisa.

🎬 *Narração:* "Toda API tem uma 'bula'. A da Transparência usa Swagger — uma página
onde dá pra ver os endpoints e até testar no navegador. Vamos conhecer o nosso."

### 2a. Explorar o Swagger
1. 🖱️ Abra a documentação interativa:
   👉 https://api.portaldatransparencia.gov.br/swagger-ui/index.html
2. 🖱️ Procure o grupo **Novo Bolsa Família** → endpoint
   `GET /novo-bolsa-familia-por-municipio`.
3. 👀 Repare nos parâmetros:

   | Parâmetro | Obrigatório | Exemplo | Descrição |
   |-----------|:-----------:|---------|-----------|
   | `mesAno` | ✅ | `202401` | Ano + mês (AAAAMM) |
   | `codigoIbge` | ✅ | `3550308` | Código IBGE do município (7 díg.) |
   | `pagina` | ❌ | `1` | Página da paginação (padrão 1) |

   - **Base URL:** `https://api.portaldatransparencia.gov.br/api-de-dados`
   - 🎬 Aproveite para citar os **limites**: 30 req/min (dia) · 90 req/min (madrugada) ·
     estouro = `429`. (Detalhes em [`api-limites.md`](api-limites.md).)

### 2b. Primeira chamada de verdade
Pelo terminal (PowerShell ou bash), com a chave no `.env`:

```bash
curl "https://api.portaldatransparencia.gov.br/api-de-dados/novo-bolsa-familia-por-municipio?mesAno=202401&codigoIbge=3550308&pagina=1" \
  -H "chave-api-dados: SUA_CHAVE"
```

- 👀 **Com a chave** → `200` e um JSON com o `valor` pago e `quantidadeBeneficiados`
  de São Paulo (jan/2024).
- ⚠️ **Sem a chave** → `401 - Chave de API não informada`. (Vale mostrar o erro de propósito.)

🎬 *Narração:* "Esse JSON é o nosso dado bruto. Cada município, num mês, vira um registro
desses. Nosso pipeline vai pegar isso de **5.571 municípios** e organizar na nuvem."

> 📎 Estrutura completa da resposta e campos em [`api-endpoints.md`](api-endpoints.md).

💲 **Custo:** zero.

---

## Passo 3 — Conseguir a tabela de municípios (IBGE) — a dimensão 🗺️

**Objetivo:** obter a lista oficial dos **5.571 municípios** com seus **códigos IBGE**.
Por que **antes** do Bolsa Família? Porque o endpoint dos fatos **exige o `codigoIbge`** —
sem essa tabela, não temos como pedir os dados município a município. Ela é a nossa
**dimensão** (tabela de referência) que enriquece os fatos lá na frente.

🎬 *Narração:* "Repara numa coisa: pra pedir o Bolsa Família de uma cidade, a API quer o
**código IBGE** dela. Então, antes dos fatos, a gente precisa da lista de municípios.
Essa lista vem de outra fonte pública e gratuita: a **API de Localidades do IBGE**."

### 3a. Apresentar a API do IBGE (navegando pelo site)
Vamos navegar pela documentação oficial do IBGE até o recurso de municípios — assim o
aluno vê que é uma API pública, organizada e gratuita.

1. 🖱️ Abra o portal de serviços de dados do IBGE:
   👉 https://servicodados.ibge.gov.br/api/docs
   - 👀 Aparece uma lista de **APIs em cards** (Agregados, Calendário, CNAE, **Localidades**,
     Malhas Geográficas, Nomes, Notícias…).
2. 🖱️ Clique no card **Localidades**
   ("Obtenha os dados sobre as divisões administrativas do Brasil").
   - 👀 Abre a doc da API de Localidades com um **Sumário** lateral listando os recursos:
     `AglomeracaoUrbana`, `Distritos`, `Mesorregioes`, `Microrregioes`, **`Municipios`**,
     `Paises`, `Regioes`, `UFs`, etc.
3. 🖱️ No sumário, clique em **Municipios** → **Municípios**
   ("Obtém o conjunto de municípios do Brasil").
   - 👀 A página mostra o método **`GET /localidades/municipios`**, os parâmetros opcionais
     (ordenação/visão) e um exemplo de resposta.
4. 🖱️ Abra a chamada real direto no navegador (é um `GET` aberto, **sem chave**):
   👉 https://servicodados.ibge.gov.br/api/v1/localidades/municipios
   - 👀 O navegador mostra um **JSON gigante** — um objeto por município, com a hierarquia
     aninhada (`microrregiao → mesorregiao → UF → regiao`).
   - 🎬 *Narração:* "Uma única chamada traz o Brasil inteiro. Repara que vem **aninhado** —
     a gente vai **achatar** isso numa tabela plana, que é o formato que banco e SQL gostam."
5. 👀 Aponte um município de exemplo: o campo `id` é o **código IBGE** (ex.: São Paulo = `3550308`),
   o mesmo que usamos no Passo 2.

### 3b. Preparar o ambiente local (uma vez só)
```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r src/lambda/requirements.txt
```

### 3c. Gerar a tabela (1 chamada → CSV plano)
```bash
./.venv/Scripts/python.exe src/build_dim_municipios.py
# -> data/dim_municipios.csv (5.571 municípios)
```
- 👀 O script baixa o JSON do IBGE, **achata** a hierarquia e salva o CSV ordenado por UF e nome.
- 👀 Colunas geradas: `codigo_ibge, municipio, uf_sigla, uf_nome, uf_codigo, regiao_sigla,
  regiao_nome, mesorregiao, microrregiao`.
- 🖱️ Abra `data/dim_municipios.csv` (Excel ou VS Code) e mostre as primeiras linhas —
  fica concreto pro aluno ver "a tabela".

🎬 *Narração:* "Pronto: saímos de um JSON aninhado pra uma tabela limpa de 5.571 linhas.
Essa é a primeira 'tabela' do nosso projeto — guarda ela, porque é a chave que liga
município ↔ código IBGE no resto do curso."

### ✅ Validação do Passo 3
- `data/dim_municipios.csv` tem **5.571 linhas** (+1 cabeçalho).
- A coluna `codigo_ibge` tem 7 dígitos; conferir que São Paulo aparece como `3550308`.

💲 **Custo:** zero — IBGE é gratuito e roda local.

---

## Passo 4 — Baixar os fatos do Bolsa Família (primeira coleta local) 🪜

**Objetivo:** sair do "olhar a API" para "salvar o dado". Agora que temos os códigos IBGE
(Passo 3), coletamos os **fatos** localmente, em poucos municípios, gerando os JSONs
**no mesmo layout particionado** que usaremos no S3.

🎬 *Narração:* "Com a lista de municípios na mão, agora sim a gente busca os valores do
Bolsa Família. Em vez de baixar à mão um por um, usamos um coletor em Python que já resolve
três coisas que vão nos perseguir o curso todo: respeitar o limite da API, tentar de novo
quando dá 429, e não rebaixar o que já baixou."

### 4a. Coletar os fatos — comece pequeno
```bash
# 5 municípios de SP, ~10s
./.venv/Scripts/python.exe src/ingestao_api.py --ano 2024 --mes 1 --uf SP --limite 5
```
- 👀 O coletor lê os `codigo_ibge` da dim (Passo 3) e pede o Bolsa Família de cada um.
- 👀 Os JSONs saem em:
  ```
  data/raw/bolsa_familia/ano=2024/mes=01/uf=SP/municipio=*.json
  ```
  Esse é **exatamente** o layout `ano=/mes=/uf=/municipio=` que recriaremos no S3.

### 4b. Mostrar os 3 conceitos-chave do coletor
🖱️ Abra `src/ingestao_api.py` na tela e aponte:
- **Intervalo de ~2,1s** entre chamadas → respeita o rate limit (30/min).
- **Retry em `429`** → robustez quando estoura o limite.
- **Skip de arquivos já baixados** → idempotência (rodar 2× mostra `pulados=5`).

🎬 *Narração:* "Guarda esses três nomes: **rate limit**, **retry** e **idempotência**.
Quando a gente transformar isso numa Lambda lá na AWS, eles voltam — só que serverless."

### ✅ Validação do Passo 4
- JSONs na estrutura `ano=/mes=/uf=/municipio=`.
- Rodar o mesmo comando de novo → `pulados=5` (idempotência ok).

💲 **Custo:** zero — tudo na sua máquina.

---

## Passo 5 — Blindar a conta AWS (MFA, usuário IAM, alarme de billing, CLI) 🛡️

**Objetivo:** entrar na AWS de forma **segura** e, antes de criar qualquer recurso, ligar
a **rede de segurança contra cobranças** (alarme de billing). Este passo não cria nada que
custe — é a fundação que protege o resto do curso.

> **Contexto deste curso:** você **já tem conta AWS** e usaremos a região **us-east-1 (N. Virginia)**.
> ⚠️ O alarme de billing (métrica `EstimatedCharges`) **só existe em us-east-1** — mesmo que
> você crie recursos em outra região, o alarme mora aqui.

🎬 *Narração:* "Antes de criar um único bucket, a gente faz duas coisas que todo profissional
faz: para de usar o usuário 'dono da conta' pra tudo, e liga um alarme que avisa por e-mail
se a fatura passar de um valor. Assim você dorme tranquilo."

### 5a. Login e conferir quem você é
1. 🖱️ Acesse https://console.aws.amazon.com e faça login.
2. 🖱️ No canto **superior direito**, confira a **região = N. Virginia (us-east-1)**.
3. 👀 Clique no seu nome (canto superior direito): se aparecer **"Root user"**, vamos sair
   desse hábito nos próximos sub-passos e passar a usar um **usuário IAM**.

### 5b. MFA na conta root (proteção máxima)
1. 🖱️ Logado como **root**, abra **IAM** (busque "IAM" na barra superior).
2. 🖱️ Menu lateral → **Security credentials** (ou banner "Add MFA" no painel).
3. 🖱️ Em **Multi-factor authentication (MFA)** → **Assign MFA device**.
4. ⌨️ Dê um nome, escolha **Authenticator app**, e escaneie o QR com Authy/Google Authenticator.
5. ⌨️ Digite **dois códigos consecutivos** para confirmar.
   - 👀 O dispositivo MFA aparece listado como ativo.

### 5c. Criar (ou conferir) seu usuário IAM
> Se você já tem um usuário IAM com MFA, só **confirme** que existe e pule pra 5d.
1. 🖱️ IAM → **Users** → **Create user**.
2. ⌨️ Nome (ex.: `carlos-admin`) → marque **Provide user access to the Management Console**.
3. 🖱️ Permissões → **Attach policies directly** → marque **`AdministratorAccess`**
   (ok para curso/sandbox; em produção seria mais restrito).
4. 🖱️ Crie o usuário e **guarde a URL de login do IAM** (algo como
   `https://SEU_ID.signin.aws.amazon.com/console`).
5. 🖱️ Ative **MFA também nesse usuário** (mesmo fluxo do 5b).
6. 🖱️ **Saia do root** e **entre de novo como o usuário IAM** — daqui pra frente usamos ele.
   - 🎬 *Narração:* "Pronto, o root agora fica guardado. No dia a dia, esse usuário aqui."

### 5d. Alarme de billing (essencial — faça sem pular!) 💲
1. 🖱️ Garanta que a região é **us-east-1**.
2. 🖱️ Menu da conta (canto sup. dir.) → **Billing and Cost Management** →
   **Billing preferences** → ative **Receive Billing Alerts** (Alert preferences).
3. 🖱️ Abra **CloudWatch** → menu lateral **Alarms** → **All alarms** → **Create alarm**.
4. 🖱️ **Select metric** → **Billing** → **Total Estimated Charge** → métrica
   **`EstimatedCharges`** (moeda **USD**) → **Select metric**.
5. ⌨️ Condição: **Greater than** → limite **`5`** (US$ 5). Período: 6 horas (padrão serve).
6. 🖱️ **Notification** → crie um **tópico SNS** novo → informe **seu e-mail**.
   - ⚠️ Você recebe um e-mail "**Subscription Confirmation**" da AWS — **clique em Confirm**,
     senão o alarme não consegue te notificar.
7. ⌨️ Dê um nome ao alarme (ex.: `billing-5-usd`) → **Create alarm**.
   - 👀 O alarme aparece em CloudWatch → Alarms (provavelmente em estado *Insufficient data*
     no começo — normal, ele precisa de algumas horas de métrica).

🎬 *Narração:* "Esse alarme de 5 dólares é barato de consciência: se qualquer coisa escapar
do Free Tier, a AWS te manda um e-mail antes de virar problema."

### 5e. AWS CLI (para os passos automatizados mais à frente)
1. ⌨️ Confirme a instalação:
   ```bash
   aws --version
   ```
   (Se não tiver, instale o **AWS CLI v2** pelo site oficial da AWS.)
2. 🖱️ Gere uma **Access Key**: IAM → seu usuário → **Security credentials** →
   **Create access key** → caso de uso **Command Line Interface (CLI)**.
3. ⌨️ Configure o perfil:
   ```bash
   aws configure
   # AWS Access Key ID: ...
   # AWS Secret Access Key: ...
   # Default region name: us-east-1
   # Default output format: json
   ```
4. ⌨️ Valide:
   ```bash
   aws sts get-caller-identity
   ```
   - 👀 Retorna seu `Account` e o `Arn` do **usuário IAM** (não do root).
   > ⚠️ A Access Key é segredo — **nunca** comite no Git. Trate como a chave da API.

### ✅ Validação do Passo 5
- Login no console feito como **usuário IAM** (não root) e o **MFA pediu o código**.
- Alarme **`EstimatedCharges`** visível em CloudWatch → Alarms (us-east-1) e e-mail SNS **confirmado**.
- `aws sts get-caller-identity` retorna `Account` + `Arn` do seu usuário IAM.

💲 **Custo:** zero. MFA, IAM, CLI e alarme de billing são **gratuitos**.

---

## Passo 6 — Criar o bucket S3 (data lake) e entender o layout 🪣

**Objetivo:** criar o **bucket** que será nosso data lake e entender o **layout de prefixos**
(camadas `raw`/`curated`). Importante: neste passo o bucket fica **vazio de propósito** —
quem o preenche são as **Lambdas** (Passo 8+), via API, sem upload manual.

> ⚠️ Nome de bucket é **único no mundo inteiro**. Neste curso usamos
> `transparencia-datalake-us-east-1-training` (escolha um nome só seu se for refazer).

🎬 *Narração:* "O S3 é o 'HD infinito' da AWS. Aqui mora todo o nosso dado: o cru, que chega
da API, e o tratado, depois do processamento. A gente cria a caixa agora; encher fica pras Lambdas."

### 6a. Criar o bucket
1. 🖱️ Console → busque **S3** → **Create bucket**.
2. ⌨️ **Bucket name:** `transparencia-datalake-us-east-1-training`.
3. 🖱️ **Region:** **US East (N. Virginia) us-east-1** (a mesma do curso).
4. 🖱️ **Block all public access:** deixe **MARCADO** (todos os 4) — dados **não** são públicos.
   - 🎬 *Narração:* "Dado de cidadão não fica público. Esse bloqueio aqui é inegociável."
5. 🖱️ Resto no padrão → **Create bucket**.
   - 👀 O bucket aparece na lista do S3.

### 6b. Entender o layout de prefixos (só explicar, não criar)
🖱️ Abra o bucket e mostre que ele está vazio. Explique a estrutura que **vai** existir:
```
s3://transparencia-datalake-us-east-1-training/
├── raw/dim_municipios/dim_municipios.csv          ← dimensão (Lambda dim)
├── raw/bolsa_familia/ano=2024/mes=01/uf=SP/municipio=3550308.json   ← fatos (Lambda worker)
├── curated/bolsa_familia/ano=2024/mes=01/part-*.parquet            ← tratado (Glue)
└── _checkpoints/202401.json                       ← progresso da coleta
```
- **`raw`** = bronze (dado cru, como veio da API). **`curated`** = silver (limpo, em Parquet).
- O **particionamento** `ano=/mes=/uf=` é o mesmo que você viu localmente no Passo 4 —
  ele deixa as consultas no Athena mais rápidas e baratas.

### 6c. (Opcional, só para o vídeo) ver um upload pela UI
> O fluxo real **não** sobe arquivo à mão. Mas, se quiser mostrar a tela de upload ao aluno,
> dá pra subir o `data/dim_municipios.csv` em `raw/dim_municipios/` só para ilustrar — e
> depois **apagar**, deixando claro que "na prática quem faz isso é a Lambda".
1. 🖱️ Dentro do bucket → **Create folder** `raw/` (opcional) → **Upload** → escolha o CSV.
2. 🖱️ Apague em seguida para o bucket voltar ao estado "vazio, à espera da Lambda".

### ✅ Validação do Passo 6
```bash
aws s3 ls s3://transparencia-datalake-us-east-1-training/
```
- 👀 Sem erro (bucket existe). Vazio agora; após o Passo 8 mostrará `raw/...` preenchido **sem upload manual**.

💲 **Custo:** Free Tier dá **5 GB** de S3 por 12 meses. Nossos dados são poucos MB → **~zero**.

---

## Passo 7 — Guardar a chave da API no Secrets Manager 🔐

**Objetivo:** tirar a `chave-api-dados` do `.env` local e colocá-la num **cofre na nuvem**,
de onde a Lambda vai lê-la com permissão IAM — sem hardcode, sem vazar no Git/logs.

🎬 *Narração:* "Lá no começo a chave ficou num arquivo `.env` na nossa máquina. Mas a Lambda
roda na nuvem — ela não tem o nosso `.env`. A forma certa de entregar um segredo pra ela é
um cofre: o **Secrets Manager**."

### 7a. Criar o segredo
1. 🖱️ Console → busque **Secrets Manager** → **Store a new secret**.
2. 🖱️ **Secret type:** **Other type of secret**.
3. ⌨️ Em **Key/value**, adicione um par:
   - **Key:** `chave-api-dados`
   - **Value:** *(cole a sua chave da API, a mesma do `.env`)*
   > 💡 Alternativa: aba **Plaintext** e cole só a string. O `handler.py` aceita os **dois** formatos
   > (string pura **ou** `{"chave-api-dados": "..."}`).
4. 🖱️ **Encryption key:** deixe o padrão (`aws/secretsmanager`). **Next**.
5. ⌨️ **Secret name:** `portal-transparencia/chave-api-dados`. **Next**.
6. 🖱️ **Rotation:** deixe **desativada** por enquanto. **Next** → **Store**.
   - 👀 O segredo aparece na lista do Secrets Manager.

### 7b. Validar pela CLI
```bash
aws secretsmanager get-secret-value \
  --secret-id portal-transparencia/chave-api-dados \
  --query SecretString --output text
```
- 👀 Retorna sua chave (string pura ou o JSON com ela).

🎬 *Narração:* "Repara: a chave nunca apareceu no código. A Lambda vai pedir ela ao cofre
em tempo de execução, e só ela vai ter permissão pra isso — a gente configura essa permissão
no próximo passo, junto com a Lambda."

> 🔗 No Passo 8, a role da Lambda recebe a permissão `secretsmanager:GetSecretValue`
> **apenas** neste segredo (least privilege).

### ✅ Validação do Passo 7
- Segredo `portal-transparencia/chave-api-dados` existe no Secrets Manager (us-east-1).
- O comando da CLI retorna a chave correta.

💲 **Custo:** ⚠️ Secrets Manager **não tem Free Tier** — ~**US$ 0,40/mês** por segredo
(+ frações de centavo por chamada). É centavo, mas existe; por isso o Passo de limpeza (módulo 09)
**remove** o segredo no fim do curso.

---

## Passo 8 — Subir as Lambdas (dim + worker) pela UI ⚡

**Objetivo:** levar o coletor para a nuvem como **duas** Lambdas:
- **`transparencia-ingestao-dim`** — busca os municípios no IBGE e grava a dim no S3
  (é quem **enche o bucket** que ficou vazio no Passo 6, sem upload manual).
- **`transparencia-ingestao-worker`** — busca os fatos do Bolsa Família **em lotes**, com
  checkpoint/idempotência/retry (os 3 conceitos do Passo 4, agora serverless).

> 🔑 **Ordem importa:** o worker **lê a dim do S3** como lista de trabalho. Então rode a
> **dim primeiro**; só depois o worker.
> ⏱️ **Por que lotes:** 5.571 municípios × ~2s ≈ **3h** > teto de **15 min** da Lambda. Cada
> invocação faz um pedaço (~400) e **retoma** pelo checkpoint.

🎬 *Narração:* "Aquele script que rodou na nossa máquina agora vira função na nuvem. Mesma
lógica de chamar a API — muda o destino (vai pro S3) e ganha um truque pra caber no limite de
15 minutos da Lambda: ela processa um lote, anota onde parou, e continua na próxima rodada."

### 8a. A Layer do `requests`
O `boto3` já vem no runtime; o `requests` **não** — ele entra por uma **Layer**.
Há dois caminhos (use o **A**, que é o que fizemos no curso):

**A) Layer pública Klayers (mais simples — recomendado)**
Não precisa empacotar nada: usamos uma Layer pronta e pública. Para **Python 3.14**:
```
arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p314-requests:5
```
> 💡 Klayers (https://github.com/keithrozario/Klayers) publica Layers prontas de libs
> populares. Confira o ARN da sua **região** e **versão de Python** no repositório.

**B) Construir a sua própria Layer (alternativa, bom de mostrar o conceito)**
```bash
mkdir -p layer/python
./.venv/Scripts/python.exe -m pip install requests -t layer/python
cd layer && zip -r ../requests-layer.zip python && cd ..
```
1. 🖱️ Lambda → **Layers** → **Create layer**.
2. ⌨️ Nome `requests-layer` → **Upload** `requests-layer.zip` → runtime **Python 3.14** → **Create**.

### 8b. Criar a IAM Role da Lambda (least privilege)
1. 🖱️ IAM → **Roles** → **Create role** → **AWS service** → **Lambda**.
2. 🖱️ Anexe **`AWSLambdaBasicExecutionRole`** (logs no CloudWatch).
3. 🖱️ Depois de criar, **Add permissions → Create inline policy** com **3** permissões:
   - `s3:GetObject`, `s3:PutObject` no `arn:aws:s3:::transparencia-datalake-us-east-1-training/*`
     (objetos);
   - `s3:ListBucket` no `arn:aws:s3:::transparencia-datalake-us-east-1-training` (o bucket,
     **sem** o `/*`) — ⚠️ veja o box abaixo, é fácil esquecer;
   - `secretsmanager:GetSecretValue` no ARN do segredo `portal-transparencia/chave-api-dados`.
4. ⌨️ Nome da role: `transparencia-ingestao-worker-role`.
   - 🎬 *Narração:* "A função só pode fazer exatamente isto: ler/escrever no nosso bucket e ler
     um segredo específico. Nada além. Isso é least privilege."

> ⚠️ **Gotcha real (aconteceu no nosso deploy):** sem `s3:ListBucket`, um `GetObject` num
> objeto que **ainda não existe** (ex.: o checkpoint na 1ª execução) retorna **`AccessDenied`**
> em vez de **`NoSuchKey`** — o S3 esconde a existência do objeto de quem não pode listar.
> Como o código espera `NoSuchKey` para assumir "começar do zero", ele **quebra** com
> AccessDenied. A cura é exatamente esse `s3:ListBucket` no ARN do **bucket**.
> 🎬 *Narração:* "Erro clássico de IAM: não é que faltou ler o objeto — faltou poder
> **listar** o bucket pra saber que ele não existe ainda."

### 8c. Criar a Lambda da dim (`handler_dim.py`)
1. 🖱️ Lambda → **Create function** → **Author from scratch**.
2. ⌨️ Nome `transparencia-ingestao-dim` → runtime **Python 3.14**.
3. 🖱️ **Permissões/role** — a dim precisa de **`s3:PutObject`** (ela grava o CSV). Duas opções:
   - **Simples:** reusar a `transparencia-ingestao-worker-role` (já tem PutObject no bucket); ou
   - **Least-privilege:** role própria com `s3:PutObject` **escopado** a
     `arn:aws:s3:::transparencia-datalake-us-east-1-training/raw/dim_municipios/*`
     (a dim só escreve esse prefixo — não lê segredo nem outros objetos).
4. 🖱️ Cole o conteúdo de `src/lambda/handler_dim.py` → **Handler:** `handler_dim.handler` → **Deploy**.
5. 🖱️ **Configuration → General:** Timeout **120s** ⚠️ (o `handler_dim.py` chama o IBGE com
   `timeout=60`; os **3s** padrão do console **não** cabem — foi o que travou a 1ª versão).
   Memory 256 MB.
6. 🖱️ **Environment variables:** `BUCKET = transparencia-datalake-us-east-1-training`
   (a dim **não** precisa de `SECRET_NAME` — a API do IBGE é aberta).
7. 🖱️ Anexe a **Layer do `requests`** (a dim também usa `requests` — Klayers do 8a serve).

> 🟢 **Validado ao vivo via CLI:** apaguei o `dim_municipios.csv` do S3 e invoquei a dim com
> payload `{}` → retorno `{"municipios": 5571, "destino": "s3://.../raw/dim_municipios/dim_municipios.csv"}`
> e o CSV **reapareceu** (456.917 bytes) — sem nenhum `aws s3 cp`. É a prova de que a dim
> popula o lake sozinha.

### 8d. Criar a Lambda worker (`handler.py`)
1. 🖱️ Lambda → **Create function** → nome `transparencia-ingestao-worker` → **Python 3.14** →
   role existente `transparencia-ingestao-worker-role`.
2. 🖱️ Cole `src/lambda/handler.py` → **Handler:** `handler.handler` → **Deploy**.
3. 🖱️ **Layers → Add a layer:**
   - **Klayers (8a-A):** *Specify an ARN* → cole `arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p314-requests:5`; ou
   - **Própria (8a-B):** *Custom layers* → `requests-layer`.
4. 🖱️ **Configuration → General:** Timeout **15 min**, Memory **256 MB**.
   > 🎬 *Dica de demo:* para a gravação, deixe o timeout em **60s**. Assim **um** invoke fecha
   > um **lote curto** (~20 municípios), salva o checkpoint e retorna em segundos — perfeito
   > para mostrar "lote + checkpoint" sem esperar os ~14 min de um lote cheio.
5. 🖱️ **Environment variables:**
   | Key | Value |
   |-----|-------|
   | `BUCKET` | `transparencia-datalake-us-east-1-training` |
   | `SECRET_NAME` | `portal-transparencia/chave-api-dados` |
   | `INTERVALO_SEG` | `2.1` *(opcional; padrão já é 2.1)* |
   | `MARGEM_SEG` | `30` *(opcional; no demo de 60s use `15`)* |

### 8e. Executar — DIM primeiro, depois o WORKER
1. ⌨️ Popular a dim (1 chamada IBGE → S3), pela CLI ou pelo botão **Test** (payload `{}`):
   ```bash
   aws lambda invoke --function-name transparencia-ingestao-dim \
     --payload '{}' --cli-binary-format raw-in-base64-out dim.json && cat dim.json
   ```
   - 👀 Agora existe `raw/dim_municipios/dim_municipios.csv` no bucket — **sem upload manual**.
2. 🖱️ Testar o worker: aba **Test** → evento:
   ```json
   { "ano": 2024, "mes": 1 }
   ```
   - 👀 A 1ª execução processa **~400 municípios** e salva o checkpoint.

### ✅ Validação do Passo 8
- Retorno do worker mostra `baixados`, `offset_final` e **`concluido: false`** (ainda faltam municípios).
  ```bash
  aws s3 ls s3://transparencia-datalake-us-east-1-training/raw/bolsa_familia/ano=2024/mes=01/ --recursive
  aws s3 cp s3://transparencia-datalake-us-east-1-training/_checkpoints/202401.json -
  ```
- Invocar de novo **continua de onde parou** (e pula os já baixados — idempotência).

> 🟢 **Validado ao vivo via CLI** (jan/2024, timeout 60s de demo):
> - Invoke 1 → `{"offset_final": 18, "baixados": 18, "concluido": false}`
> - Invoke 2 → `{"offset_final": 35, "baixados": 17, "concluido": false}` ← **retomou do 18**
> - `_checkpoints/202401.json` = `{"offset": 35, "total": 5571}`
> - 35 JSONs em `raw/bolsa_familia/ano=2024/mes=01/uf=AC/...`; ex.: Acrelândia/AC →
>   `valor: 1.632.706,00`, `quantidadeBeneficiados: 2300`.

- ⚠️ Erros comuns (todos vistos na prática):
  - `AccessDenied ... s3:ListBucket` → faltou o `s3:ListBucket` na role (8b — veja o box).
  - `Unable to import module 'requests'` → faltou anexar a Layer (8a/8d.3).
  - `KeyError: 'BUCKET'` → env var não setada (8d.5).
  - `NoSuchKey ... dim_municipios.csv` → a **dim** ainda não está no S3; rode a Lambda dim antes (8e).

💲 **Custo:** Lambda dá **1M req/mês** + 400k GB-s grátis. Nossas ~14 invocações/mês → **zero**.

---

## Passo 9 — EventBridge: reinvocar a Lambda até fechar o mês 🔁

**Objetivo:** em vez de você apertar **Test** ~14 vezes, deixar o **EventBridge Scheduler**
reinvocar o worker a cada 15 min até o mês inteiro fechar. É seguro porque o checkpoint +
idempotência (Passo 8) garantem que cada execução **retoma** sem duplicar.

🎬 *Narração:* "A Lambda fecha ~400 municípios por rodada. Para pegar os 5.571 a gente teria
que clicar 'Test' uma porção de vezes. Em vez disso, um agendador faz isso sozinho: de 15 em
15 minutos ele cutuca a função, e por causa do checkpoint ela continua exatamente de onde parou."

### 9a. Criar o agendamento
1. 🖱️ Console → **EventBridge** → **Scheduler** → **Schedules** → **Create schedule**.
2. ⌨️ Nome: `transparencia-ingestao-15min`.
3. 🖱️ **Schedule pattern → Recurring schedule → Rate-based** → a cada **15 minutes**.
   > A 30 req/min, um mês inteiro leva **~14 execuções ≈ 3,5h** de relógio.
4. 🖱️ **Flexible time window:** Off (não precisa de janela flexível).
5. 🖱️ **Target → AWS Lambda → Invoke** → função **`transparencia-ingestao-worker`**.
6. ⌨️ **Payload (input):**
   ```json
   { "ano": 2024, "mes": 1 }
   ```
7. 🖱️ Permissão: deixe o Scheduler **criar uma nova role** para invocar a Lambda (padrão).
   **Create schedule**.

> 🔑 **Conceito:** quem invoca a Lambda agora **não** é você — é o **Scheduler**. Logo ele
> precisa de uma **role própria** (trust em `scheduler.amazonaws.com`) com `lambda:InvokeFunction`.
> No console isso é o "criar nova role" do passo 7; pela CLI a gente cria explicitamente (abaixo).

### 9a-CLI. O mesmo agendamento pela CLI
```bash
# 1) Role que o Scheduler assume (trust em scheduler.amazonaws.com)
cat > scheduler-trust.json <<'JSON'
{ "Version": "2012-10-17", "Statement": [
  { "Effect": "Allow", "Principal": { "Service": "scheduler.amazonaws.com" }, "Action": "sts:AssumeRole" } ] }
JSON
aws iam create-role --role-name transparencia-scheduler-role \
  --assume-role-policy-document file://scheduler-trust.json

# 2) Permissão de invocar SÓ o worker (least privilege)
aws iam put-role-policy --role-name transparencia-scheduler-role --policy-name invoke-worker \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"lambda:InvokeFunction","Resource":"arn:aws:lambda:us-east-1:862717443882:function:transparencia-ingestao-worker"}]}'

# 3) Cria o agendamento (rate 15 min) apontando para o worker, com o payload fixo
aws scheduler create-schedule --name transparencia-ingestao-15min \
  --schedule-expression "rate(15 minutes)" \
  --flexible-time-window "Mode=OFF" \
  --target '{"Arn":"arn:aws:lambda:us-east-1:862717443882:function:transparencia-ingestao-worker","RoleArn":"arn:aws:iam::862717443882:role/transparencia-scheduler-role","Input":"{\"ano\": 2024, \"mes\": 1}"}'
```

> 🟢 **Validado ao vivo via CLI:** criei o schedule em `rate(1 minute)` (só para a demo, para
> não esperar 15 min), **sem invocar nada à mão**, e o checkpoint andou sozinho de **`offset 35` → `52`**
> em ~75s — prova de que o Scheduler dispara a Lambda. Depois ajustei para `rate(15 minutes)`
> e deixei **DISABLED** (veja 9c). Comandos para alternar:
> ```bash
> aws scheduler update-schedule --name transparencia-ingestao-15min --state ENABLED  ...  # liga
> aws scheduler get-schedule    --name transparencia-ingestao-15min --query State --output text
> ```
> ⚠️ Para uma coleta real do mês inteiro, **suba o timeout do worker para 900s** antes de ligar
> (a 60s de demo cada disparo fecha só ~17 municípios → levaria dezenas de horas):
> ```bash
> aws lambda update-function-configuration --function-name transparencia-ingestao-worker --timeout 900
> ```

### 9b. Acompanhar até fechar o mês
```bash
# o offset deve subir a cada 15 min
aws s3 cp s3://transparencia-datalake-us-east-1-training/_checkpoints/202401.json -
```
- 👀 Quando todos os 5.571 forem processados, surge o marcador:
  ```bash
  aws s3 ls s3://transparencia-datalake-us-east-1-training/raw/bolsa_familia/ano=2024/mes=01/_SUCCESS
  ```

### 9c. ⚠️ Parar o agendamento (importante!)
Depois do `_SUCCESS`, as próximas execuções só veem `pulados` (barato, mas inútil) — e
o schedule **roda pra sempre** se você não parar.
1. 🖱️ EventBridge → Scheduler → o schedule → **Disable** (ou **Delete**).
   - 🎬 *Narração:* "Terminou o mês? Desliga o agendador. Senão ele fica rodando à toa —
     barato, mas é desleixo, e a gente não deixa recurso ligado sem motivo."
2. ⌨️ Pela CLI:
   ```bash
   aws scheduler update-schedule --name transparencia-ingestao-15min --state DISABLED ...  # desliga (mantém)
   aws scheduler delete-schedule --name transparencia-ingestao-15min                       # remove de vez
   ```

### ✅ Validação do Passo 9
- O `_checkpoints/202401.json` avança sozinho a cada ~15 min.
- O marcador `_SUCCESS` aparece ao fim do mês.
- Schedule **desabilitado** após concluir.

💲 **Custo:** EventBridge Scheduler dá **14M invocações/mês** grátis → **zero**.

---

## Passo 10 — Glue (PySpark): raw JSON → curated Parquet 🔥

**Objetivo:** transformação **bronze → prata**. Pegar os milhares de JSONzinhos aninhados do
`raw/` e virar **uma tabela limpa em Parquet** no `curated/`, particionada por `ano/mes`.
É o `glue/job_bolsa_familia.py` (PySpark).

🎬 *Narração:* "Os dados estão na nuvem, mas crus: milhares de arquivos pequenos, cheios de
campos aninhados. Pra analisar, a gente precisa achatar isso numa tabela. Esse é o trabalho do
Glue — um Spark serverless que lê tudo, organiza e regrava num formato bom pra SQL: o Parquet."

### 10a. O que o job faz (5 etapas)
1. **Lê** `raw/bolsa_familia/.../*.json`. 2. **`explode()`** o array → 1 linha por registro.
3. **Achata** (`municipio.uf.sigla` → `uf_sigla`, `tipo.descricao` → `programa`…).
4. **Deriva `ano`/`mes`** da `dataReferencia`. 5. **Grava Parquet** particionado em
`curated/bolsa_familia/ano=/mes=/` (overwrite dinâmico = idempotente por partição).

### 10b. Pela UI (console)
1. 🖱️ Suba o script: **S3** → `scripts/job_bolsa_familia.py`.
2. 🖱️ **Glue** → **ETL jobs** → **Script editor** → tipo **Spark**, Python → aponte o script.
3. 🖱️ **IAM role do Glue** (ler `raw/`, escrever `curated/`).
4. ⌨️ **Job details → Job parameters:** `--BUCKET` = `transparencia-datalake-us-east-1-training`.
5. 🖱️ **Workers:** G.1X, **2** (volume pequeno). **Glue version** 4.0.
6. 🖱️ **Run** e acompanhe em **Runs**.

### 10c. Pela CLI (o que rodamos)
```bash
# role do Glue (trust glue.amazonaws.com) + managed AWSGlueServiceRole + inline S3
aws iam create-role --role-name transparencia-glue-role --assume-role-policy-document file://glue-trust.json
aws iam attach-role-policy --role-name transparencia-glue-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole
aws iam put-role-policy --role-name transparencia-glue-role --policy-name s3-raw-curated \
  --policy-document file://glue-s3-policy.json   # GetObject /*, Put/Delete em curated*, ListBucket

# script -> S3
aws s3 cp glue/job_bolsa_familia.py s3://transparencia-datalake-us-east-1-training/scripts/job_bolsa_familia.py

# cria o job e roda
aws glue create-job --name transparencia-glue-bolsa-familia \
  --role arn:aws:iam::862717443882:role/transparencia-glue-role \
  --command '{"Name":"glueetl","ScriptLocation":"s3://transparencia-datalake-us-east-1-training/scripts/job_bolsa_familia.py","PythonVersion":"3"}' \
  --glue-version "4.0" --worker-type G.1X --number-of-workers 2 \
  --default-arguments '{"--BUCKET":"transparencia-datalake-us-east-1-training","--enable-continuous-cloudwatch-log":"true","--continuous-log-logGroup":"/aws-glue/jobs/transparencia-bolsa-familia"}'
aws glue start-job-run --job-name transparencia-glue-bolsa-familia
```

> ⚠️ **Gotcha real 1 — `curated_$folder$` (403):** o committer do Spark cria um **marcador de
> pasta** `curated_$folder$` **na raiz do bucket**, fora de `curated/`. Se a policy liberar só
> `curated/*`, dá **AccessDenied**. Cura: liberar `curated*` (sem a barra) no `s3:PutObject`.
>
> 🧠 **O que é esse marcador?** No S3 **não existem pastas** — é um namespace plano de chaves; a
> "pasta `curated/`" é só um prefixo no nome dos objetos. O Hadoop/EMR (engine do Spark do Glue)
> ainda pensa em diretórios, então grava um **objeto de 0 byte** com o sufixo histórico `_$folder$`
> para **emular** a pasta. É inofensivo — Athena/Glue **ignoram** (não vira linha nem partição) e o
> Spark recria se você apagar.

> ⚠️ **Gotcha real 2 — "não acho o log group":** o Glue **não** cria um grupo por job (≠ Lambda).
> Ele usa **grupos compartilhados** com **stream = JobRunId**:
> `/aws-glue/jobs/output` (stdout/`print`), `/aws-glue/jobs/error` (stack trace),
> `/aws-glue/jobs/logs-v2` (contínuo). Para um grupo **próprio e fácil de achar**, passe
> `--continuous-log-logGroup /aws-glue/jobs/transparencia-bolsa-familia` (foi o que fizemos).
> No console: **Glue → o job → aba Runs → clique no run → Output/Error/Continuous logs**.

### ✅ Validação do Passo 10
```bash
aws s3 ls s3://transparencia-datalake-us-east-1-training/curated/bolsa_familia/ --recursive | head
```
> 🟢 **Validado ao vivo via CLI:** job `SUCCEEDED` (~278s, 2 DPU); log de saída
> `OK: 1268 linhas gravadas`; Parquet em `curated/bolsa_familia/ano=2026/mes=4/part-*.snappy.parquet`.

💲 **Custo:** ⚠️ Glue **NÃO tem Free Tier** — ~US$ 0,44/DPU-h, mín. 2 DPU, por segundo. Cada run
pequeno ≈ **centavos**. Rode **sob demanda** (não em loop) e remova no teardown.

---

## Passo 11 — Athena: SQL serverless sobre o curated 🔎

**Objetivo:** consultar o Parquet com **SQL puro**, sem servidor. O capstone: **top 15 que mais
e que menos recebem**. O Athena consulta o S3 através de **tabelas no Glue Data Catalog**.

🎬 *Narração:* "Agora a parte que todo mundo entende: SQL. O Athena lê direto o Parquet no S3,
sem banco de dados pra subir. Só precisamos 'apresentar' os arquivos pra ele como **tabelas** —
e aí é `SELECT` à vontade."

### 11a. Pré-requisito — local de resultados
O Athena grava o resultado de cada query no S3. Defina uma pasta:
`s3://transparencia-datalake-us-east-1-training/athena-results/`
(no console: **Athena → Settings → Manage → Query result location**).

### 11b. Catalogar as tabelas (DDL no editor do Athena)
> Alternativa ao Glue Crawler (módulo 07): aqui criamos as tabelas **na mão**, o que é ótimo
> didaticamente porque o aluno **vê o schema**.
```sql
CREATE DATABASE IF NOT EXISTS transparencia;

-- fato: Parquet particionado
CREATE EXTERNAL TABLE IF NOT EXISTS transparencia.bolsa_familia (
  id bigint, data_referencia date, codigo_ibge string, municipio string,
  uf_sigla string, regiao_nome string, programa string,
  valor double, qtd_beneficiados bigint
) PARTITIONED BY (ano int, mes int)
STORED AS PARQUET
LOCATION 's3://transparencia-datalake-us-east-1-training/curated/bolsa_familia/';

-- registra as partições existentes (ano=/mes=)
MSCK REPAIR TABLE transparencia.bolsa_familia;

-- dimensão: CSV com cabeçalho
CREATE EXTERNAL TABLE IF NOT EXISTS transparencia.dim_municipios (
  codigo_ibge string, municipio string, uf_sigla string, uf_nome string,
  uf_codigo string, regiao_sigla string, regiao_nome string,
  mesorregiao string, microrregiao string
) ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
STORED AS TEXTFILE
LOCATION 's3://transparencia-datalake-us-east-1-training/raw/dim_municipios/'
TBLPROPERTIES ('skip.header.line.count'='1');
```
> 💡 `MSCK REPAIR TABLE` é o passo que **descobre as partições** no S3. Sem ele, a tabela existe
> mas retorna 0 linhas. (Rode de novo sempre que surgir um `ano/mes` novo.)

### 11c. Conferência e capstone
```sql
-- quantas linhas por partição
SELECT ano, mes, COUNT(*) municipios, ROUND(SUM(valor),2) valor_total
FROM transparencia.bolsa_familia GROUP BY ano, mes ORDER BY ano, mes;

-- TOP 15 que MAIS recebem (troque 2026/2024 conforme o mês coletado)
WITH fato AS (
  SELECT codigo_ibge, SUM(valor) valor_ano, SUM(qtd_beneficiados) benef
  FROM transparencia.bolsa_familia WHERE ano = 2026 GROUP BY codigo_ibge)
SELECT d.municipio, d.uf_sigla, d.regiao_nome, ROUND(f.valor_ano,2) valor, f.benef
FROM fato f JOIN transparencia.dim_municipios d ON d.codigo_ibge = f.codigo_ibge
ORDER BY f.valor_ano DESC LIMIT 15;

-- TOP 15 que MENOS recebem (valor > 0 ignora quem não teve pagamento)
WITH fato AS (
  SELECT codigo_ibge, SUM(valor) valor_ano, SUM(qtd_beneficiados) benef
  FROM transparencia.bolsa_familia WHERE ano = 2026 GROUP BY codigo_ibge)
SELECT d.municipio, d.uf_sigla, d.regiao_nome, ROUND(f.valor_ano,2) valor, f.benef
FROM fato f JOIN transparencia.dim_municipios d ON d.codigo_ibge = f.codigo_ibge
WHERE f.valor_ano > 0
ORDER BY f.valor_ano ASC LIMIT 15;
```

### 11d. Resultados (validados ao vivo via CLI)
Conferência: `2024/1` → 69 municípios · `2026/4` → **1.360** municípios, R$ **4,78 bi**
(parcial — coleta de abril em andamento).

**TOP 15 que MAIS recebem (abr/2026):**
| # | Município | UF | Valor (R$) | Benef. |
|---|---|---|--:|--:|
| 1 | Salvador | BA | 187.691.407 | 289.522 |
| 2 | Fortaleza | CE | 181.399.942 | 276.950 |
| 3 | Manaus | AM | 159.059.425 | 228.735 |
| 4 | Brasília | DF | 103.270.931 | 150.264 |
| 5 | São Luís | MA | 75.914.541 | 113.524 |
| … | _(Maceió, Feira de Santana, Macapá, Goiânia, Caucaia…)_ | | | |

**TOP 15 que MENOS recebem (abr/2026, `valor > 0`):**
| # | Município | UF | Valor (R$) | Benef. |
|---|---|---|--:|--:|
| 1 | Fundão | ES | **112** | 1.635 ⚠️ |
| 2 | Anhanguera | GO | 44.428 | 66 |
| 3 | Aloândia | GO | 76.799 | 116 |
| 4 | Diorama | GO | 83.939 | 128 |
| … | _(majoritariamente municípios pequenos de GO)_ | | | |

> 🎬 **Dois ganchos de aula:**
> - **Anomalia (data quality):** Fundão/ES com R$ 112 para 1.635 beneficiários (≈ R$ 0,07/pessoa)
>   é um **outlier** — provável ajuste/estorno na fonte. Lição: `valor > 0` **não** garante qualidade.
>   Para o ranking "limpo", use um piso: `WHERE f.valor_ano > 1000`.
> - **Viés da coleta parcial:** o "menos recebem" está dominado por **GO** porque o worker coleta por
>   ordem de UF e ainda não chegou em SP/RS/SC etc. São **dados em movimento** — rode de novo após o
>   `_SUCCESS` (e o re-run do Glue) e o ranking muda. Por isso **SP e Rio não aparecem** no "mais".

💲 **Custo:** Athena cobra **~US$ 5 por TB escaneado**. Parquet+partição fazem a query ler
**KBs** → frações de centavo. (Boa prática que já aplicamos: colunar + partição = query barata.)

---

## Próximos passos (a preencher conforme avançamos)

- **Passo 12** — **Monitoramento & teardown**: CloudWatch, custos e **limpeza** para não gerar
  cobrança — incluindo apagar **Glue job**, **Secret**, **Scheduler** e esvaziar o **bucket** (módulo 09).

> 🔁 **Como usamos este doc:** você executa o passo no console/portal, me diz o que
> apareceu na tela (ou onde travou), e eu ajusto/escrevo o próximo passo aqui com o
> texto e a narração já prontos para a gravação.

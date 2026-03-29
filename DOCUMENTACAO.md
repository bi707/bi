# 📊 Meta Ads → Google Sheets

Automação que exporta o relatório de campanhas do Meta Ads Manager e envia para o Google Sheets, rodando 2x por dia no seu computador.

---

## O que essa automação faz?

```
Meta Ads Manager  →  CSV  →  Google Sheets
```

1. Abre o navegador automaticamente
2. Entra no Meta Ads Manager com sua conta
3. Seleciona o período **do dia 1º do mês atual até hoje**
4. Clica em "Exportar como .csv"
5. Envia os dados para a planilha **Meta Ads - Campanhas** no Google Sheets
6. Repete esse processo **2x por dia** (8h e 20h) via Agendador de Tarefas

---

## Pré-requisitos instalados

| Ferramenta | Versão | Para que serve |
|---|---|---|
| Python | 3.14 | Roda os scripts |
| Git | 2.53 | Baixa e atualiza o projeto |
| Playwright (Chromium) | 1.51 | Controla o navegador |
| gspread | 6.1.2 | Envia dados ao Google Sheets |

---

## Arquivos do projeto

```
C:\Users\Vanessa\bi\
│
├── scrape_campaigns.py   ← Exporta o CSV do Meta Ads Manager
├── upload_sheets.py      ← Envia o CSV para o Google Sheets
├── run.bat               ← Roda os dois scripts em sequência (usado pelo agendador)
│
├── credentials.json      ← Chave do Google (não compartilhar!)
├── session.json          ← Sessão salva do Facebook (gerada automaticamente)
├── .env                  ← Configurações e senhas (não compartilhar!)
│
├── reports\              ← Pasta onde os CSVs são salvos
│   └── campanhas_YYYY-MM-DD_YYYY-MM-DD.csv
│
└── meta_ads\             ← Módulo de conexão com a API do Meta
```

---

## Configurações (.env)

O arquivo `.env` guarda todas as credenciais do projeto:

```
META_APP_ID           → ID do app no Meta for Developers
META_APP_SECRET       → Senha do app no Meta for Developers
META_ACCESS_TOKEN     → Token de acesso à API do Meta
META_AD_ACCOUNT_ID    → ID da conta de anúncios (ex: act_415126871085547)
META_FB_EMAIL         → E-mail do Facebook usado no Ads Manager
META_FB_PASSWORD      → Senha do Facebook
```

> ⚠️ **Nunca compartilhe esse arquivo.** Ele contém todas as senhas.

---

## Configuração do Google Sheets

A integração usa uma **Conta de Serviço** do Google para escrever na planilha sem precisar de login manual.

### O que foi feito:
1. Criado projeto `analytics-contas` no Google Cloud
2. Ativada a **Google Sheets API**
3. Criada conta de serviço: `meta-ads-sheets@analytics-contas.iam.gserviceaccount.com`
4. Baixada a chave JSON → salva como `credentials.json` na pasta do projeto
5. Planilha **Meta Ads - Campanhas** compartilhada com a conta de serviço como **Editor**

### Onde fica a planilha:
Acesse pelo Google Drive ou pelo link que aparece ao rodar `upload_sheets.py`.
Nome da planilha: **Meta Ads - Campanhas** → aba **Campanhas**

> A planilha é **sobrescrita** a cada atualização (não acumula histórico).

---

## Como rodar manualmente

Abra o Prompt de Comando (`cmd`) e rode:

```
cd C:\Users\Vanessa\bi
python scrape_campaigns.py
python upload_sheets.py
```

Ou rode os dois de uma vez:

```
cd C:\Users\Vanessa\bi
run.bat
```

---

## Agendamento automático (2x por dia)

Configurado no **Agendador de Tarefas do Windows**:

| Campo | Valor |
|---|---|
| Nome da tarefa | Meta Ads - Atualização |
| Programa | `C:\Users\Vanessa\bi\run.bat` |
| Horários | 8h e 20h, todos os dias |

Para verificar ou editar: Tecla Windows → `Agendador de Tarefas` → procure a tarefa **Meta Ads - Atualização**.

---

## Situações comuns

### O navegador abriu e pediu login
Isso acontece quando a sessão expira (normalmente a cada 30-90 dias).
Faça o login manualmente no navegador que abriu — depois ele continua sozinho e salva a sessão.

### Apareceu código de SMS / verificação
Complete a verificação manualmente. Após confirmar, a sessão é salva e não pede mais até expirar.

### O CSV ficou em branco / "Nenhum dado encontrado"
- Verifique se a conta de anúncios correta está no `.env` (`META_AD_ACCOUNT_ID`)
- Confira se há campanhas ativas no período

### Precisa trocar a conta de anúncios
Abra o arquivo `.env` e altere a linha:
```
META_AD_ACCOUNT_ID=act_NOVO_ID_AQUI
```

### Preciso atualizar o projeto
Abra o Prompt de Comando e rode:
```
cd C:\Users\Vanessa\bi
git pull
```

---

## Contas e acessos utilizados

| Serviço | Conta |
|---|---|
| Meta Ads Manager | bi@mdass.com.br |
| Google Cloud | (conta usada para criar o projeto `analytics-contas`) |
| Google Sheets | Planilha: **Meta Ads - Campanhas** |

---

---

## Etapa B — API Oficial + Nuvem (Google Cloud)

Substitui o scraping pelo navegador pela **API oficial do Meta**, rodando na **nuvem**.

### Vantagens sobre a Etapa A

| | Etapa A (scraping) | Etapa B (API + nuvem) |
|---|---|---|
| Computador precisa estar ligado | Sim | **Não** |
| Risco de bloqueio pelo Meta | Sim | **Nenhum** |
| Login manual periódico | Sim (a cada 30-90 dias) | **Não** |
| Coluna "Resultados" com nome amigável | Não | **Sim** |

### Arquivos da Etapa B

```
cloud/
├── main.py          ← Código da Cloud Function
└── requirements.txt ← Dependências da Cloud Function

deploy_cloud.py      ← Script de deploy (roda uma vez só)
```

### Como funciona na nuvem

```
Cloud Scheduler (8h e 20h)
    → Cloud Function (meta-ads-sheets)
        → API do Meta → busca campanhas do mês atual
        → Google Sheets → atualiza a planilha
```

### Como fazer o deploy

**1.** Instale o Google Cloud SDK:
Acesse **cloud.google.com/sdk/docs/install** e instale o **Google Cloud CLI**

**2.** Abra o Prompt de Comando e faça login:
```
gcloud auth login
```

**3.** Rode o script de deploy (faz tudo automaticamente):
```
cd C:\Users\Vanessa\bi
python deploy_cloud.py
```

O script vai:
- Habilitar as APIs necessárias no Google Cloud
- Fazer o deploy da Cloud Function
- Configurar o agendamento automático (8h e 20h, horário de Brasília)

### Coluna "Resultados" na Etapa B

A Etapa B busca automaticamente os **nomes reais das conversões personalizadas** da conta (ex: "Approved Profiling", "Completed Profiling") diretamente da API do Meta, gerando colunas com os mesmos nomes que aparecem no Gerenciador de Anúncios.

### Etapa A ainda funciona?

**Sim.** Os scripts `scrape_campaigns.py`, `upload_sheets.py` e `run.bat` continuam intactos. A Etapa B é um complemento — ambas escrevem na mesma planilha **Meta Ads - Campanhas**.

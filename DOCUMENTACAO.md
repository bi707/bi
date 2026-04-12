# Documentação: Automação Meta Ads → Google Sheets

**Projeto:** Kuna Capital — Relatório Diário de Campanhas  
**Conta de anúncios:** Kuna Capital Ad Account (`act_415126871085547`)  
**Pasta do projeto:** `C:\Users\Vanessa\bi`  
**Última atualização:** Abril 2026

---

## O que essa automação faz?

Todo dia de manhã (às 8h), o seu computador executa automaticamente os seguintes passos:

```
Meta Ads Manager
   ↓  envia e-mail às ~3h com o relatório do mês
Gmail (bi@mdass.com.br)
   ↓  script lê o e-mail e extrai o link de download
Browser invisível (Playwright/Chromium)
   ↓  abre o link usando sua sessão salva do Facebook
Arquivo CSV
   ↓  planilha atualizada automaticamente
Google Sheets → "Meta Ads - Campanhas" → aba "Campanhas"
```

O resultado na planilha cobre **do dia 1 do mês até o dia anterior**, com todas as campanhas detalhadas por dia, incluindo a coluna "Resultados" (conversões de pixel offsite — os dados que só aparecem no gerenciador do Meta, não pela API oficial).

---

## Estrutura de arquivos

```
C:\Users\Vanessa\bi\
│
├── run_planc_local.py      ← SCRIPT PRINCIPAL (roda todo dia às 8h)
├── run.bat                 ← Atalho que o Task Scheduler executa
│
├── scrape_campaigns.py     ← Usado só para RENOVAR a sessão do Facebook
├── upload_sheets.py        ← Utilitário para envio manual de CSV
│
├── gmail_auth.py           ← Usado só UMA VEZ para autorizar o Gmail
│
├── .env                    ← Credenciais Meta Ads (NÃO commitar no Git!)
├── credentials.json        ← Chave da Service Account do Google (NÃO commitar!)
├── gmail_credentials.json  ← Chave OAuth do Gmail (NÃO commitar!)
├── gmail_token.json        ← Token de acesso ao Gmail (NÃO commitar!)
├── session.json            ← Sessão salva do Facebook (NÃO commitar!)
│
├── requirements.txt        ← Lista de dependências Python
├── cloud/                  ← Código da Cloud Function (backup/referência)
└── reports/                ← CSVs exportados localmente (backup)
```

> **Regra de ouro:** Os 5 arquivos marcados com "NÃO commitar" contêm senhas e tokens. Eles já estão no `.gitignore`. Nunca os adicione ao Git nem os compartilhe por e-mail.

---

## Contas e serviços utilizados

| Serviço | Conta | Para que serve |
|---|---|---|
| Meta Ads Manager | bi@mdass.com.br | Relatório agendado de campanhas |
| Gmail | bi@mdass.com.br | Receber o e-mail com o link do CSV |
| Google Cloud Project | analytics-contas | APIs habilitadas |
| Google Sheets | Compartilhado com Service Account | Destino dos dados |
| GitHub | bi707/bi | Controle de versão do código |

---

## Credenciais e onde cada uma fica

### 1. `.env` — Credenciais do Meta Ads
**Arquivo:** `C:\Users\Vanessa\bi\.env`

```
META_APP_ID=...          ← ID do aplicativo Meta (Meta for Developers)
META_APP_SECRET=...      ← Chave secreta do aplicativo
META_ACCESS_TOKEN=...    ← Token de acesso à API (expira, precisa renovar anualmente)
META_AD_ACCOUNT_ID=...   ← ID da conta de anúncios (act_XXXXXXXXX)
META_FB_EMAIL=...        ← E-mail de login do Facebook
META_FB_PASSWORD=...     ← Senha do Facebook
```

> **Usado por:** `scrape_campaigns.py` (para abrir o Meta Ads Manager)

### 2. `credentials.json` — Service Account do Google
**Arquivo:** `C:\Users\Vanessa\bi\credentials.json`  
**De onde veio:** Google Cloud Console → Projeto `analytics-contas` → IAM → Service Accounts → Chave JSON

É como uma "conta de serviço robô" que tem permissão de editar a planilha. A planilha `Meta Ads - Campanhas` precisa estar compartilhada com o e-mail dessa service account (algo como `...@analytics-contas.iam.gserviceaccount.com`).

> **Usado por:** `run_planc_local.py`, `upload_sheets.py`

### 3. `gmail_credentials.json` — OAuth do Gmail
**Arquivo:** `C:\Users\Vanessa\bi\gmail_credentials.json`  
**De onde veio:** Google Cloud Console → Projeto `analytics-contas` → APIs → Gmail API → Credenciais OAuth 2.0 → Tipo: Desktop

Permite que o script leia e-mails da conta `bi@mdass.com.br`.

> **Usado por:** `gmail_auth.py` (apenas no setup inicial)

### 4. `gmail_token.json` — Token de acesso ao Gmail
**Arquivo:** `C:\Users\Vanessa\bi\gmail_token.json`  
**De onde veio:** Gerado automaticamente por `gmail_auth.py`

Contém o token de acesso e o **refresh token** — isso significa que se o token de acesso expirar (acontece a cada hora), ele se renova sozinho sem precisar de interação humana.

> **Válido por:** Indefinidamente (o refresh token não expira, a menos que você revogue o acesso no Google Account)  
> **Usado por:** `run_planc_local.py`

### 5. `session.json` — Sessão do Facebook
**Arquivo:** `C:\Users\Vanessa\bi\session.json`  
**De onde veio:** Gerado por `scrape_campaigns.py` quando você faz login

Contém os cookies de autenticação do Facebook (equivale a "estar logado" no browser). O script usa esses cookies para baixar o CSV sem precisar abrir um browser visível.

> **Válido por:** ~60 a 90 dias (sessões do Facebook expiram)  
> **Usado por:** `run_planc_local.py`, `scrape_campaigns.py`

---

## Configurações no Meta Ads Manager

### Relatório agendado (pré-configurado)
- **Onde:** Meta Ads Manager → Relatórios → Relatórios personalizados → Exportação agendada
- **Nome:** Campanhas
- **Conta:** Kuna Capital Ad Account
- **Período:** Mês atual (do dia 1 até o dia anterior)
- **Frequência:** Diária, às ~3h da manhã (horário de Brasília)
- **Destino:** bi@mdass.com.br
- **Formato:** CSV

O Meta envia um e-mail de `advertise-noreply@support.facebook.com` com o assunto:
`"Sua exportação do Gerenciador de Anúncios da Meta está pronta: Kuna Capital Ad Account, Campanhas, ..."`

---

## Windows Task Scheduler — Agendamento às 8h

O agendamento foi criado para rodar `run.bat` automaticamente às 8h todos os dias.

**Para verificar se está configurado:**
1. Abra o menu Iniciar → pesquise "Agendador de Tarefas"
2. Procure por uma tarefa chamada algo como `MetaAdsBI` ou similar
3. Deve estar configurado para rodar `C:\Users\Vanessa\bi\run.bat`

**Para recriar o agendamento manualmente (se necessário):**
1. Abra o Agendador de Tarefas
2. Clique em "Criar Tarefa Básica"
3. Nome: `MetaAdsBI`
4. Trigger: Diariamente às 8:00
5. Ação: Iniciar programa → `C:\Users\Vanessa\bi\run.bat`
6. Marque "Executar mesmo que o usuário não esteja conectado"
7. Marque "Executar com privilégios mais altos"

---

## Setup do zero (se precisar refazer tudo)

> Siga essa seção somente se estiver configurando em um computador novo ou recriando tudo do zero.

### Pre-requisitos

- Python 3.11 ou superior instalado
- Git instalado
- Google Chrome instalado (o Playwright usa um Chromium próprio separado)

### Passo 1 — Clonar o repositório

```cmd
cd C:\Users\Vanessa
git clone https://github.com/bi707/bi.git bi
cd bi
git checkout claude/meta-ads-integration-rxetK
```

### Passo 2 — Instalar as dependências Python

```cmd
pip install -r requirements.txt
pip install google-api-python-client google-auth-httplib2 beautifulsoup4
playwright install chromium
```

> `playwright install chromium` baixa o browser Chromium que o script usa. Precisa de internet e cerca de 200 MB de espaço.

### Passo 3 — Criar o arquivo `.env`

Crie um arquivo chamado `.env` (com ponto na frente, sem extensão) em `C:\Users\Vanessa\bi\` com o conteúdo abaixo. Substitua pelos valores reais se necessário:

```
META_APP_ID=1481245430330902
META_APP_SECRET=6976e37f9d3e80cfe2f17b47ae4b2b88
META_ACCESS_TOKEN=EAAVDL1OzNhYB...
META_AD_ACCOUNT_ID=act_415126871085547
META_FB_EMAIL=bi@mdass.com.br
META_FB_PASSWORD=Bi@1234
```

> **Como criar no Windows:** Abra o Bloco de Notas, cole o conteúdo acima, vá em "Salvar como", mude "Tipo" para "Todos os arquivos" e salve com o nome `.env` (incluindo o ponto).

### Passo 4 — Obter `credentials.json` (Service Account do Google)

1. Acesse: https://console.cloud.google.com
2. Selecione o projeto `analytics-contas`
3. Menu esquerdo → IAM e administrador → Contas de serviço
4. Selecione a conta de serviço existente (ou crie uma nova com papel de Editor)
5. Aba "Chaves" → "Adicionar chave" → "Criar nova chave" → JSON
6. O arquivo baixa automaticamente. Renomeie para `credentials.json` e mova para `C:\Users\Vanessa\bi\`

> **Importante:** A planilha `Meta Ads - Campanhas` no Google Sheets precisa estar compartilhada (como Editor) com o e-mail da service account (algo como `nome@analytics-contas.iam.gserviceaccount.com`).

### Passo 5 — Obter `gmail_credentials.json` (OAuth do Gmail)

1. Acesse: https://console.cloud.google.com → Projeto `analytics-contas`
2. Menu → APIs e Serviços → Credenciais
3. Clique em "+ Criar Credenciais" → "ID do cliente OAuth"
4. Tipo de aplicativo: **Aplicativo para computador** (Desktop app)
5. Nome: pode ser qualquer coisa, ex: `MetaAdsLocal`
6. Clique em Criar → Baixe o JSON
7. Renomeie para `gmail_credentials.json` e salve em `C:\Users\Vanessa\bi\`

> Se aparecer aviso de "App não verificado" durante a autorização, clique em "Avançado" → "Acessar MetaAdsLocal (não seguro)". Isso é normal para aplicativos internos.

### Passo 6 — Autorizar o Gmail (uma vez só)

```cmd
cd C:\Users\Vanessa\bi
pip install google-auth-oauthlib
python gmail_auth.py
```

Um browser vai abrir pedindo para fazer login com `bi@mdass.com.br` e autorizar o acesso ao Gmail. Após autorizar, o arquivo `gmail_token.json` é criado automaticamente em `C:\Users\Vanessa\bi\`.

### Passo 7 — Criar a sessão do Facebook

```cmd
python scrape_campaigns.py
```

Um browser Chrome vai abrir. Faça login com `bi@mdass.com.br` e confirme o código de segurança (SMS/e-mail). Após entrar no Meta Ads Manager, o script salva automaticamente a sessão em `session.json` e fecha.

> **Dica:** Se o Facebook pedir "confiar neste dispositivo" ou "este é seu dispositivo?", confirme sempre. Isso faz a sessão durar mais tempo (60–90 dias).

### Passo 8 — Testar o script principal

```cmd
python run_planc_local.py
```

Saída esperada:
```
=== Plano C Local: Gmail → CSV → Google Sheets ===

Conectando ao Gmail...
Conectando ao Google Sheets...
Buscando e-mail do Meta...
  E-mail: Sua exportação do Gerenciador de Anúncios da Meta está pronta: ...
  Link: https://www.facebook.com/ads/report_builder/...

Baixando CSV...
  Abrindo link no browser (headless)...
  Download concluído: Kuna-Capital-Ad-Account-Campanhas-...csv
  81 linhas de dados.

Atualizando Google Sheets...

Concluído! Planilha: https://docs.google.com/spreadsheets/d/...
```

Se aparecer essa mensagem, tudo está funcionando.

### Passo 9 — Configurar o Task Scheduler (agendamento às 8h)

Veja as instruções na seção "Windows Task Scheduler" acima.

---

## Manutenção periódica

### Renovar a sessão do Facebook (a cada 60–90 dias)

**Sintoma:** O script falha com erro no download, ou aparece mensagem de "sessão expirada".

**Por que acontece:** Os cookies do Facebook em `session.json` expiram periodicamente. É como ser desconectado automaticamente do Facebook depois de um tempo.

**Como corrigir (5 minutos):**

```cmd
cd C:\Users\Vanessa\bi
python scrape_campaigns.py
```

Faça login no browser que abrir. Confirme o código de segurança se pedir. O `session.json` é atualizado automaticamente. Teste em seguida:

```cmd
python run_planc_local.py
```

---

### Quando o Gmail token parar de funcionar

**Sintoma:** Erro como `Token has been expired or revoked` ou `invalid_grant`.

**Por que acontece:** Raramente acontece. Pode ocorrer se o acesso ao Gmail for revogado manualmente no Google Account, ou se a senha mudar.

**Como corrigir:**

```cmd
cd C:\Users\Vanessa\bi
python gmail_auth.py
```

Autorize novamente. O `gmail_token.json` é sobrescrito com um novo token.

---

### Quando o relatório não aparecer no e-mail

**Sintoma:** Script mostra `Nenhum e-mail do Meta encontrado nos últimos 3 dias`.

**Como verificar:**
1. Abra o Gmail de `bi@mdass.com.br`
2. Procure por e-mails de `advertise-noreply@support.facebook.com`
3. Se não houver, o relatório agendado no Meta pode ter parado

**Como reativar no Meta Ads Manager:**
1. Acesse: https://adsmanager.facebook.com
2. Menu → Relatórios → Relatórios personalizados
3. Procure por "Campanhas" → verifique se a exportação agendada está ativa
4. Se não estiver, recrie:
   - Período: Mês atual
   - Frequência: Diária
   - Destino: bi@mdass.com.br
   - Formato: CSV

---

### Quando a planilha não atualizar (sem erro aparente)

**Possíveis causas e verificações:**
1. O computador estava desligado às 8h → a automação não rodou. Execute manualmente: `python run_planc_local.py`
2. A Service Account perdeu acesso à planilha → abra a planilha → Compartilhar → verifique se o e-mail da service account está como Editor

---

## Operação diária (resumo)

| Hora | O que acontece | Quem faz |
|---|---|---|
| ~3h da manhã | Meta gera e envia o relatório por e-mail | Meta (automático) |
| 8h | Task Scheduler executa `run.bat` | Windows (automático) |
| 8h | `run.bat` chama `run_planc_local.py` | Script (automático) |
| 8h + ~1 min | Planilha atualizada com dados do mês | Script (automático) |

**Você não precisa fazer nada**, desde que:
- O computador esteja ligado às 8h
- A sessão do Facebook ainda seja válida (dura 60–90 dias)

---

## Solução de problemas rápida

| Mensagem de erro | Causa mais provável | Solução |
|---|---|---|
| `session.json não encontrado` | Arquivo foi deletado ou nunca criado | Rodar `scrape_campaigns.py` |
| Facebook retorna página de erro no download | Sessão expirada | Rodar `scrape_campaigns.py` para renovar |
| `gmail_token.json não encontrado` | Arquivo foi deletado | Rodar `gmail_auth.py` |
| `Nenhum e-mail encontrado` | Relatório não chegou ou chegou há mais de 3 dias | Verificar caixa de entrada + relatório agendado no Meta |
| `Spreadsheet not found` | Nome da planilha mudou ou acesso revogado | Verificar nome exato e compartilhamento com Service Account |
| `playwright: executable not found` | Playwright não instalado | Rodar `playwright install chromium` |
| `ModuleNotFoundError` | Dependência Python faltando | Rodar `pip install -r requirements.txt` |

---

## Arquivos que NÃO ficam no Git (segredos)

Esses arquivos existem apenas no computador local e nunca devem ser enviados ao GitHub:

| Arquivo | Conteúdo | Consequência se vazar |
|---|---|---|
| `.env` | Senha do Facebook, tokens Meta | Acesso à conta de anúncios |
| `credentials.json` | Chave da Service Account | Acesso e edição da planilha |
| `gmail_credentials.json` | Chave OAuth Gmail | Pode ser usada para criar novos tokens |
| `gmail_token.json` | Token ativo do Gmail | Leitura de todos os e-mails |
| `session.json` | Cookies de sessão do Facebook | Login na conta bi@mdass.com.br |

O arquivo `.gitignore` já bloqueia o envio acidental desses arquivos.

---

## Por que esse caminho foi escolhido (histórico técnico)

Esta seção existe para que qualquer pessoa que venha dar manutenção entenda por que o sistema funciona como funciona.

### Por que não usamos a API oficial do Meta?

A Meta Marketing API retorna dados de campanhas, mas a coluna "Resultados" que aparece no gerenciador de anúncios é calculada com base em **conversões de pixel offsite** (eventos como "Approved Profiling" e "Completed Profiling"). Esses eventos não estão disponíveis como ação padrão na API de insights. Os números retornados pela API são diferentes dos que aparecem na interface, tornando a comparação impossível.

### Por que não rodamos na nuvem (Google Cloud)?

Tentamos rodar na Google Cloud Functions. O script funciona até a etapa de download, mas o Facebook **bloqueia requisições de download de relatórios vindas de IPs de datacenters** (Google Cloud, AWS, Azure, etc.) — mesmo com cookies válidos e browser real. A resposta é uma página de erro 400. Isso é uma proteção intencional do Facebook contra acesso programático em massa. Funciona apenas a partir de IPs residenciais ou comerciais normais.

### Por que o script usa Playwright (browser invisível) em vez de requests direto?

O Facebook aplica **TLS fingerprinting**: analisa a "assinatura digital" da conexão para distinguir um browser real de um script Python. A biblioteca `requests` tem uma assinatura diferente de um Chrome real. Mesmo enviando os cookies corretos, o Facebook rejeita a requisição com erro 400. O Playwright abre um Chromium real e passa por essa verificação.

### Por que a sessão precisa ser renovada periodicamente?

O Facebook invalida cookies de sessão por segurança após 60–90 dias de inatividade, ou quando detecta atividade suspeita. A renovação é feita rodando `scrape_campaigns.py`, que abre um browser real, faz login e salva os novos cookies em `session.json`.

---

## Recursos e links úteis

| Recurso | Link |
|---|---|
| Meta Ads Manager | https://adsmanager.facebook.com |
| Google Cloud Console | https://console.cloud.google.com |
| Google Sheets (planilha) | https://docs.google.com/spreadsheets/d/1Kk-5NVR6oej1VAF_PKTJtLIpoVwfH_hb60yxdiUU1H0 |
| Repositório do código | https://github.com/bi707/bi |
| Branch de desenvolvimento | `claude/meta-ads-integration-rxetK` |

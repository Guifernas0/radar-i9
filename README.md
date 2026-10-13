# Radar i9+ — P2 - Agente de IA para Clipping de Comunicação

> **Na nuvem, sem depender de nenhum PC:** [`PUBLICAR-NA-NUVEM.md`](PUBLICAR-NA-NUVEM.md) (passo a passo, custo zero).
> **Instalar no Mac:** [`COMECE-AQUI.md`](COMECE-AQUI.md) (duplo clique, sem terminal). **Apresentar:** [`ROTEIRO-DEMO.md`](ROTEIRO-DEMO.md).

## Novidades de 10/2026: Painel completo na nuvem

No Painel publicado (Streamlit Community Cloud) agora funcionam **Coletar agora**, **Testar a IA**, **Enviar e-mail de teste**,
**Configurações** e **Avaliação da IA** — tudo pelo GitHub, protegido pela `SENHA_PAINEL` (ADR [0002](docs/adr/0002-painel-na-nuvem-grava-pelo-github.md),
código em `src/radar/nuvem.py`). O `radar.db` foi unificado: histórico da nuvem + o que só existia no Mac.

## Novidades de 09/2026 (a partir de `materiais-vs-radar.md`)

| Pedido da i9+ | Onde está |
|---|---|
| E-mail no mesmo dia com tag "leia hoje" (reunião 27/08) | `coleta.py` + `correio.py`: Alerta = marca **+** Relevância >= `[alerta] relevancia_minima` (8), coletadas nos últimos 2 dias, no máx. `max_itens` |
| Assunto padrão do Manual de Envio de E-mail | `projeto = "P2 - ..."` no `config.toml` prefixa Alerta e Digest |
| Detalhe concreto em vez do título | campo `destaque` da IA; é a frase grande dos cartões "Leia hoje" |
| Eixos Tecnologia/Mercado/Legislação/ESG (C14) e ESG (mockup) | `eixos.py`; campos `tema` e `esg`. Histórico antigo migrado por regra de palavras (`origem = "regra"`); `uv run radar reclassificar` refaz com a IA |
| Traduzir termos técnicos | campo `termos_tecnicos` → aba **Glossário** |
| "O que é relevante para a i9+?" | `[ia] criterios` no `config.toml`, editável no Painel |
| Fontes citadas (Congresso, WEF, GBA) + termos novos | `[[feeds]]` Câmara/Senado com `filtro` de palavras; Termos com `rotulo` (ex.: `site:weforum.org`) |
| Veracidade da fonte | `fontes_conhecidas` → selo "fonte conhecida" + filtro |
| Linha do tempo, nuvem de palavras, filtro de Relevância (C23–C25) | aba **Gráficos** e barra lateral |
| KPIs do Intel Hub | 6 números no topo (eficiência do filtro, favorabilidade ESG…) |
| Teste de precisão humano × IA (C19) | aba **Avaliação da IA** (tabela `avaliacoes`, F1) |
| Entrega 1 e 2 (diagrama, fontes, JSON) e LGPD | aba **Como funciona** |
| Rodar no PC do Parceiro (ticket 09) | `.command` do Mac, botão **Coletar agora**, aba **Configurações** (grava `.env`/`config.toml` local), agendamento via launchd |
| Cota grátis da IA | `[ia] max_por_coleta`, `pausa_segundos`; para após 5 falhas seguidas; sem chave, pula a IA |

Correções: o `.env` agora ignora comentário no fim da linha (antes `GEMINI_API_KEY=   # ...` virava a "chave");
o Painel não quebra com Menção ainda sem resumo; Painel local só escuta `localhost`.

Robô que acorda sozinho todo dia, busca no Google News as notícias sobre a i9+/InoveMais e o setor
(baterias de segunda vida, economia circular, energia), resume com IA gratuita, guarda tudo num
histórico que nunca descarta nada, avisa por e-mail no mesmo dia quando a marca é citada, manda um
Digest a cada N dias e mostra tudo num Painel na web. **Custo zero: sem cartão, sem servidor, sem domínio.**

Projeto de Extensão "TI e Sociedade" — Universidade Positivo, Equipe 6 (ADS), parceiro i9+ Baterias e Energia.

- Vocabulário do projeto: [`CONTEXT.md`](CONTEXT.md) · Decisões: [`docs/adr/`](docs/adr/) · Spec e tickets: [`.scratch/radar-i9/`](.scratch/radar-i9/)
- Cotas gratuitas verificadas em 2026: [`docs/research/free-tiers-2026.md`](docs/research/free-tiers-2026.md)

## Como a equipe trabalha no código

Este repositório é a referência (o robô roda aqui todo dia às 8h e o Painel https://radar-i9.streamlit.app republica a cada
commit na `main`). Pra trabalhar sem depender de ninguém, cada frente da equipe usa um **fork**:

1. Clique em **Fork** (canto superior direito). Vira `seu-usuario/radar-i9`, uma cópia inteira sua.
2. No fork, *Settings → Collaborators* pra dar acesso a quem for trabalhar junto.
3. O que não vem no fork (10 min, tudo descrito neste README):
   - *Settings → Secrets and variables → Actions*: `GEMINI_API_KEY` (chave grátis, seção "Configurar"); `SMTP_USER`/`SMTP_PASS`
     quando existir o Gmail do projeto. Enquanto não tem SMTP: **Variables** → `RADAR_SIMULAR_ENVIO` = `1`.
   - Aba **Actions** → *enable* (fork vem com o cron desligado) → *radar → Run workflow* pra testar.
   - Painel do fork no Streamlit (seção "Painel na web"); nos Secrets do Streamlit, `GITHUB_TOKEN`, `SENHA_PAINEL` e
     `RADAR_REPO = "seu-usuario/radar-i9"`; nas Variables do GitHub, `RADAR_LINK_PAINEL` (ver `PUBLICAR-NA-NUVEM.md`).
4. Quando algo estiver pronto, abra um **Pull Request** do fork pra cá — ou siga só no fork, tanto faz.

**O que falta** está nas [Issues](https://github.com/tiagoalgauer/radar-i9/issues). Pegue uma, comente "peguei", comente "feito"
ao terminar. Etiquetas: `sem-codigo` (conta, reunião, config), `codigo` (mexe em `.py`), `secrets` (Secrets do GitHub/Streamlit —
quem faz é o dono do repositório onde o robô roda, ou seja, do fork).

Regras pra ninguém derrubar o que está no ar:

1. Trabalhe em branch: `git switch -c minha-mudanca` → commit → `git push -u origin minha-mudanca` → Pull Request.
2. Outro colega revisa e faz o merge quando o check `testes` estiver verde.
3. **Não commite `radar.db`.** O robô commita ele todo dia; se aparecer no seu `git status` depois de um `uv run radar`, rode `git restore radar.db`.
4. Antes de abrir o PR: `git pull --rebase origin main` e `uv run pytest`.
5. Quebrou a `main` (Painel com erro)? `git revert <commit>` + push — o Painel volta em 1–2 min.

Mudanças que **não precisam de git**: Termos → aba *Configurações* do Painel (quando o token estiver configurado) ou
editar `config.toml` direto no GitHub (seções abaixo). Feeds e e-mails → `config.toml` no GitHub (lápis → *Commit changes*).

## Como funciona (uma Coleta)

1. Lê `config.toml` (Termos, Intervalo, destinatários).
2. Para cada Termo × idioma, busca no Google News RSS (`when:2d`).
3. Ignora o que já está no histórico (hash do link). **Nada é apagado, nunca.**
4. Cada Menção nova vai à IA: resumo em português, Relevância 0–10, tema, sentimento. Se a IA falhar,
   a Menção fica guardada com o título como resumo e é reprocessada na próxima Coleta.
5. Menção que cita `InoveMais`/`i9+` (Termos de marca) → **Alerta de marca** por e-mail no mesmo dia.
6. Se passaram N dias do último Digest → **Digest** (marca no topo, depois por Relevância, top 20 + link do Painel).
7. Grava `radar.db` de volta no repositório (no GitHub Actions).

## Rodar no seu PC

```bash
uv sync                      # instala (precisa do uv: https://docs.astral.sh/uv/)
cp .env.example .env         # preencha as chaves (opcional — sem elas roda em modo simulado)
uv run radar                 # uma Coleta completa
uv run pytest                # testes (sem internet, sem chave)
```

Sem `SMTP_USER`/`SMTP_PASS` o e-mail é **simulado** (impresso na tela, ninguém recebe). Sem
`GEMINI_API_KEY` as Menções são guardadas sem resumo e reprocessadas quando a chave existir.

### Comandos de fumaça (testam cada peça contra o mundo real)

```bash
uv run radar fumaca fonte    # busca no Google News e mostra o que achou por Termo
uv run radar fumaca ia       # manda uma notícia de exemplo ao Gemini (ou Groq) e mostra a resposta
uv run radar fumaca email    # envia um e-mail de teste para o próprio SMTP_USER
```

## Robô na nuvem (GitHub Actions) — ticket 06

O workflow `.github/workflows/radar.yml` roda todo dia às 08:00 (Curitiba) e por clique
(*Actions → radar → Run workflow*). Ele coleta, resume, envia e commita o `radar.db` de volta (ADR-0001).

1. No repositório: **Settings → Secrets and variables → Actions → Secrets** → `GEMINI_API_KEY`, `SMTP_USER`, `SMTP_PASS`.
2. Enquanto os segredos não existem, ligue o **modo demonstração**: **Variables** → `RADAR_SIMULAR_ENVIO` = `1`.
   Sem essa variável e sem segredos o run **falha de propósito** (nunca um run verde que não envia nada).
3. Para demonstrar ao vivo: *Actions → radar → Run workflow*. O log mostra as linhas `coleta:`, `ia:`, `alerta de marca:`, `digest:`.

O cron do GitHub desliga se o repositório ficar 60 dias sem atividade — o commit diário do robô já conta como atividade.

## Painel na web (Streamlit Community Cloud) — tickets 07 e 08

Local: `uv run streamlit run painel.py` (abre em http://localhost:8501).

Publicar, de graça e sem domínio:

1. Entrar em https://share.streamlit.io com a conta do **GitHub** (nenhuma conta nova).
2. *Create app → Deploy a public app from GitHub* → repositório `radar-i9`, branch `main`, arquivo `painel.py`.
3. Em *App URL* escolher `radar-i9` → o endereço fica `https://radar-i9.streamlit.app`. Se mudar, atualize `link_painel` no `config.toml`.
4. O app relê o repositório a cada commit do robô, então o Painel acompanha o `radar.db` sozinho.

Depois de 12h sem ninguém abrir, o app hiberna; quem abrir espera ~15 s ele acordar (fato verificado em `docs/research/`).

## Rodar no PC da empresa (brinde — ticket 09)

O mesmo robô, sem GitHub, num Windows. Uma vez só:

1. Instalar o `uv`: abrir o **PowerShell** e colar `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
2. Baixar o projeto: `git clone https://github.com/tiagoalgauer/radar-i9.git` (ou *Code → Download ZIP* e descompactar).
3. Entrar na pasta: `cd radar-i9`.
4. Copiar `.env.example` para `.env` e preencher `GEMINI_API_KEY` (e `SMTP_USER`/`SMTP_PASS` se quiser e-mail de verdade).
5. `uv run radar` → faz uma Coleta; o histórico fica em `radar.db` **nesse PC**.
6. Painel local: `uv run streamlit run painel.py` → abre http://localhost:8501.

Sem `SMTP_USER`/`SMTP_PASS` nenhum e-mail sai (modo simulado). Para agendar todo dia sem o GitHub: *Agendador de Tarefas do Windows* → ação `uv run radar` na pasta do projeto. Testado em: _(pendente — anotar aqui o Windows e a data do primeiro teste)_.

## Plano B de IA: Groq (ticket 10)

Se a cota gratuita do Gemini mudar: criar uma chave grátis em https://console.groq.com (sem cartão), guardar como
`GROQ_API_KEY` (Secret do GitHub ou `.env`) e trocar no `config.toml`:

```toml
[ia]
provedor = "groq"
modelo = "openai/gpt-oss-120b"
```

Nada mais muda. Teste: `uv run radar fumaca ia`.

## Fontes (ticket 11)

| Fonte | O que traz | Como configurar |
|---|---|---|
| **Google News RSS** | notícias por Termo, pt e en, últimos 2 dias | automático, por Termo |
| **Bing News RSS** | segundo índice + **trecho do corpo** (ajuda a achar a marca e a IA) | automático, por Termo |
| **Feeds fixos** (`[[feeds]]` no config) | RSS de sites (ex.: Embrapii) e **Google Alerts em modo RSS** (blogs, páginas, PDFs) | `nome` + `url` no `config.toml` |

Google Alerts: em https://www.google.com/alerts crie o alerta (ex.: `InoveMais`, `"i9+" baterias`, `site:linkedin.com InoveMais`),
em *Mostrar opções* escolha **Entregar para: Feed RSS**, copie a URL do feed e cole num `[[feeds]]`. Grátis, sem chave.
A mesma matéria vinda de duas Fontes entra uma vez (link real + título).

Fora do alcance (sem API gratuita): LinkedIn e Instagram — ver `docs/research/fontes-alem-do-google-news.md`.

## Configurar e coletar pelo Painel publicado (botões)

No PC, a aba **Configurações** grava o `config.toml` e o `.env` locais. Publicado na nuvem, o Painel faz o mesmo pelo GitHub:
Termos, destinatários, intervalo e critério da IA gravam o `config.toml` no repositório (o robô usa na próxima Coleta e o Painel
republica sozinho em 1–2 min); **Coletar agora**, **Testar a IA** e **Enviar e-mail de teste** ligam o robô no GitHub Actions;
avaliações vão para `avaliacoes.json`. Pra funcionar, três Secrets no Streamlit Cloud (app -> Settings -> Secrets):

```toml
GITHUB_TOKEN = "github_pat_..."   # fine-grained, só este repositório: Contents + Actions = Read and write
SENHA_PAINEL = "uma senha combinada com o Sandro"   # (SENHA_TERMOS, o nome antigo, também vale)
RADAR_REPO = "tiagoalgauer/radar-i9"
```

Token: GitHub -> Settings -> Developer settings -> Fine-grained tokens -> Generate; validade de 1 ano; ao vencer, gerar outro.
Passo a passo completo: [`PUBLICAR-NA-NUVEM.md`](PUBLICAR-NA-NUVEM.md).

## Adicionar ou trocar um Termo sem instalar nada

1. Abra https://github.com/tiagoalgauer/radar-i9/blob/main/config.toml e clique no lápis (**Edit**).
2. Copie um bloco `[[termos]]` existente e mude o `texto` (sem aspas dentro do texto) e os `idiomas` (`["pt"]`, `["en"]` ou os dois).
   Se for nome da empresa, coloque `marca = true` — aí dispara Alerta no mesmo dia.
3. **Commit changes** (botão verde). Pronto: o robô usa a lista nova na próxima Coleta (todo dia às 8h).
   Pra rodar na hora: aba **Actions** → *Radar* → **Run workflow**.

Quem tem permissão de editar: quem for colaborador do repositório (Settings → Collaborators). Dá pra convidar o Sandro.

## Configurar

`config.toml` — Termos (com `marca = true` para os que disparam Alerta; `idiomas = []` para só detectar
sem buscar), `intervalo_dias`, destinatários, link do Painel, provedor/modelo de IA. Termos **sem aspas**.

Variáveis de ambiente (`.env` local ou *Secrets* do GitHub):

| Variável | Para quê |
|---|---|
| `GEMINI_API_KEY` | chave do Gemini (Google AI Studio, free tier) |
| `GROQ_API_KEY` | só se `provedor = "groq"` no config (plano B) |
| `SMTP_USER` | Gmail do projeto (remetente) |
| `SMTP_PASS` | senha de app desse Gmail (exige verificação em 2 etapas) |
| `RADAR_SIMULAR_ENVIO` | qualquer valor = não envia e-mail mesmo com credenciais |
| `RADAR_LINK_PAINEL` | (Variable do GitHub) endereço do Painel publicado; sobrepõe `link_painel` do config nos e-mails |

## Estrutura

```
config.toml        Termos, Intervalo, destinatários
src/radar/
  coleta.py        uma Coleta inteira (a costura testada)
  db.py            histórico SQLite (mencoes, envios)
  fontes.py        Google News RSS, Bing News RSS e feeds fixos ([[feeds]])
  ia.py            Gemini (plano A) / Groq (plano B)
  correio.py       Alerta (marca + leia hoje), Digest, SMTP do Gmail
  eixos.py         eixos fixos de tema e ESG, normalização e regra de reserva
  ajustes.py       Painel grava .env e config.toml no PC (preserva comentários)
  termos.py        adicionar/remover Termo gravando o config.toml no GitHub (botão do Painel)
  nuvem.py         Painel publicado: liga o robô (workflow_dispatch), grava config/avaliações no GitHub, cópia de trabalho do banco
  cli.py           `uv run radar` e os comandos de fumaça
painel.py          Painel Streamlit (Leia hoje, KPIs, abas; Coletar agora e Configurações no PC)
*.command          instaladores e atalhos do Mac (scripts/mac/ tem o resto)
.github/workflows/ radar.yml = o cron diário · testes.yml = pytest em todo PR
tests/             pytest com dublês; fixtures = XML real das Fontes
radar.db           o histórico (commitado pelo robô — nunca por pessoas)
```

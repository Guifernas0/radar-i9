# Radar i9+ na nuvem — passo a passo (custo zero, ≈ 40 min)

O Radar deixa de depender do Mac. O **robô** roda no GitHub Actions todo dia às 8h (e quando alguém clica
**Coletar agora**). O **Painel** fica num endereço `https://….streamlit.app`, que abre no celular e no notebook.
Na versão publicada funcionam todas as abas do Painel, inclusive **Coletar agora**, **Configurações**
(destinatários, intervalo, critério da IA, Termos) e **Avaliação da IA**.

```
Painel (Streamlit Community Cloud) ──"Coletar agora" / Configurações / Avaliações──► GitHub (API)
        ▲                                                                              │
        │ republica sozinho a cada commit                                              ▼
   repositório no GitHub  ◄── commita radar.db ── Robô (GitHub Actions: coleta → IA → e-mails)
```

> **Por que não Cloudflare?** O Painel é um app Python (Streamlit) e precisa de um servidor Python rodando.
> O plano gratuito da Cloudflare (Workers/Pages) só roda JavaScript e páginas estáticas, então o Painel teria
> de ser reescrito. GitHub Actions + Streamlit Community Cloud rodam o código como está, de graça, sem cartão
> (ADR [0001](docs/adr/0001-robo-na-nuvem-historico-no-repo.md) e [0002](docs/adr/0002-painel-na-nuvem-grava-pelo-github.md)).

---

## Antes de começar: qual repositório?

O robô já roda todo dia em **`tiagoalgauer/radar-i9`**, e o Painel antigo está em `https://radar-i9.streamlit.app`.

- **Caminho A, recomendado:** atualizar esse repositório com esta versão. Mantém o histórico, o robô agendado
  e o endereço. Precisa do **Tiago** (dono do repositório) para os passos 1, 3 e 4, ou que ele te adicione como
  colaborador (*Settings → Collaborators*).
- **Caminho B:** criar um repositório seu (ex.: `guilhermeferrarezi/radar-i9`) e seguir todos os passos com a
  sua conta. O endereço do Painel será outro (ex.: `radar-i9-inovemais.streamlit.app`).

Esta pasta já traz o `radar.db` **unificado**: as 6.553 Menções do robô da nuvem, mais as 317 que só existiam
no Mac e as 148 análises feitas com os eixos novos. Total: 6.870 Menções, nada perdido.

---

## Passo 1 — Subir esta versão para o GitHub (10 min)

**Com GitHub Desktop** (https://desktop.github.com):

- **Caminho A:**
  1. *File → Clone repository* → `tiagoalgauer/radar-i9`.
  2. Copie **por cima** todo o conteúdo desta pasta, **menos o `.env`** (ele tem as suas chaves e já está no `.gitignore`).
  3. Escreva um resumo (ex.: "Painel completo na nuvem") → **Commit to main** → **Push origin**.
- **Caminho B:**
  1. *File → Add local repository* → escolha esta pasta → *create a repository*.
  2. **Publish repository**. Desmarque *Keep this code private* para o GitHub Actions ser ilimitado.
     As Menções são notícias públicas, e chaves nunca vão para o repositório.

> Na pasta, a pasta `.github` é oculta no Finder (Cmd+Shift+. mostra). Confira no site do GitHub se
> `.github/workflows/radar.yml` subiu.

## Passo 2 — Segredos do robô no GitHub (5 min)

No repositório: **Settings → Secrets and variables → Actions**.

| Aba | Nome | Valor |
|---|---|---|
| Secrets | `GEMINI_API_KEY` | chave grátis em https://aistudio.google.com/apikey (pode ser a mesma do seu `.env`) |
| Secrets | `SMTP_USER` | Gmail do projeto (remetente) |
| Secrets | `SMTP_PASS` | senha de app desse Gmail (16 letras) |
| Variables | `RADAR_LINK_PAINEL` | endereço do Painel (passo 4), ex.: `https://radar-i9.streamlit.app`. Vai no rodapé dos e-mails |
| Variables | `RADAR_SIMULAR_ENVIO` = `1` | **só** se ainda não houver Gmail: modo demonstração, sem enviar e-mail |

No caminho A, os três segredos provavelmente já existem. Confira e siga em frente.
No caminho B: aba **Actions → I understand… enable** (repositório novo vem com o Actions desligado).

## Passo 3 — Token para o Painel ligar o robô e gravar configurações (5 min)

Quem gera é o **dono do repositório**: o GitHub só deixa criar token para repositórios da própria conta.

1. GitHub → foto → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Preencha:
   - **Nome:** `Radar Painel`.
   - **Expiration:** 1 ano. Anote a data: quando vencer, o Painel volta a ser só leitura até gerar outro.
   - **Repository access:** *Only select repositories* → o repositório do Radar.
   - **Permissions → Repository permissions:**
     - **Contents: Read and write**, para gravar `config.toml` e `avaliacoes.json`.
     - **Actions: Read and write**, para o botão Coletar agora e para ver as rodadas do robô.
3. **Generate token** → copie (`github_pat_…`).

## Passo 4 — Publicar o Painel no Streamlit Community Cloud (10 min)

1. Entre em https://share.streamlit.io com a conta do GitHub dona do repositório.
2. Escolha o caso:
   - **Caminho A** (o app `radar-i9` já existe): no app, **⋮ → Settings**.
   - **Caminho B:** **Create app → Deploy a public app from GitHub**. Preencha:
     - **Repository:** o seu.
     - **Branch:** `main`.
     - **Main file path:** `painel.py`.
     - **App URL:** ex. `radar-i9-inovemais`.
     - **Advanced settings → Python version:** `3.13`.
3. Em **Secrets**, cole e preencha:
   ```toml
   GITHUB_TOKEN = "github_pat_..."            # passo 3
   SENHA_PAINEL = "uma senha para a equipe"   # quem souber pode coletar e mudar configurações
   RADAR_REPO = "tiagoalgauer/radar-i9"       # ou "seu-usuario/radar-i9" no caminho B
   ```
4. **Save** (ou **Deploy**). Em 2 a 4 minutos o Painel abre no endereço escolhido. Volte ao passo 2 e
   preencha `RADAR_LINK_PAINEL` com ele.

## Passo 5 — Teste de ponta a ponta (5 min)

1. Abra o Painel no **celular**: deve mostrar as 6.870 Menções.
2. Barra lateral → **Área da equipe** → digite a `SENHA_PAINEL`.
3. Aba **Configurações** → **Testar a IA** e depois **Enviar e-mail de teste**.
   - Em "Últimas rodadas do robô" aparece cada teste. Clique em **log** para ver o resultado.
   - O e-mail de teste chega no próprio Gmail do robô.
4. Barra lateral → **Coletar agora**. A rodada aparece como *na fila* e depois *rodando agora*. Em 5 a 10 minutos fica
   *concluída*, o robô commita o `radar.db` e o Painel se atualiza sozinho (recarregue a página).
5. Configurações → mude o **Digest a cada quantos dias** → **Salvar**. O commit aparece no GitHub, e o Painel
   mostra o valor novo em 1 a 2 minutos.

✅ A partir daqui o Mac pode ficar desligado.

---

## Bom saber

- **Hibernação:** se ninguém abrir o Painel por 12 h, o Streamlit o põe para dormir. Quem abrir clica em
  *"Yes, get this app back up!"* e espera ~30 s. O robô **não** dorme: ele roda no GitHub, independente do Painel.
- **Quem tem acesso:** o Painel publicado é público para leitura (são notícias públicas). Mudar qualquer coisa
  exige a `SENHA_PAINEL`. Chaves de IA e de e-mail nunca aparecem no Painel; elas ficam nos Secrets do GitHub.
- **Cron desligado após 60 dias sem atividade:** não acontece, porque o commit diário do robô conta como atividade.
- **Rodar no Mac continua funcionando**, com os mesmos `.command`. Se usar os dois, o Mac guarda um histórico próprio.
  O da nuvem é o oficial.

## Se algo der errado

| Sintoma | Causa e correção |
|---|---|
| Configurações diz "somente leitura" | Faltam `GITHUB_TOKEN` ou `SENHA_PAINEL` nos Secrets do Streamlit (passo 4). |
| "GitHub respondeu 401" | Token vencido ou colado errado. Gere outro (passo 3) e troque no Streamlit. |
| "GitHub respondeu 403" | Faltou a permissão **Actions** ou **Contents: Read and write** no token. |
| "GitHub respondeu 404" | `RADAR_REPO` errado, ou o token não inclui esse repositório. |
| "GitHub respondeu 422" | O `radar.yml` no GitHub é a versão antiga. Refaça o passo 1. |
| Rodada do robô "falhou" com `GEMINI_API_KEY não configurado` | Falta o segredo do passo 2 (ou ligue `RADAR_SIMULAR_ENVIO`). |
| Painel não mostra as notícias novas | Recarregue a página. O Streamlit leva 1 a 2 minutos após o commit do robô. |
| App com erro ao instalar | No Streamlit: *Settings → Python version 3.13* e **Reboot app**. |

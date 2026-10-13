---
status: accepted
---

# O Painel publicado faz tudo pelo GitHub e nunca escreve no radar.db do repositório

O Parceiro não tem escritório nem máquina ligada: o Painel na web precisa fazer o que o Painel do Mac faz
(Coletar agora, Configurações, avaliações), sem custo. No Streamlit Community Cloud o disco é descartável e o app é
atualizado por `git pull` a cada commit. Decidimos que, com `GITHUB_TOKEN` e `SENHA_PAINEL` nos Secrets do app:

- **Coletar agora / Testar a IA / Enviar e-mail de teste** disparam o workflow `radar.yml` (`workflow_dispatch`,
  input `acao`). Quem coleta é sempre o robô do GitHub Actions, com os segredos do repositório.
- **Configurações** (destinatários, intervalo, critério da IA, Termos) gravam o `config.toml` no repositório pela API.
- **Avaliações** (teste de precisão) gravam `avaliacoes.json` no repositório; o Painel importa esse arquivo.
- O Painel lê uma **cópia de trabalho** do `radar.db` fora do repositório (`radar/nuvem.py`), renovada quando o robô
  commita um banco novo. Escrever no arquivo versionado travaria o `git pull` do Streamlit.
- Toda escrita exige a `SENHA_PAINEL` na sessão; chaves de IA e e-mail ficam só nos Secrets do GitHub.

## Considered Options

- **Cloudflare Workers/Pages** (pedido do Parceiro, funcionou em outro projeto da equipe): o plano gratuito só roda
  JavaScript e estático; exigiria reescrever o Painel. Rejeitado.
- **Painel coletando dentro do próprio Streamlit**: o banco do app se perde a cada atualização e os segredos de IA/e-mail
  teriam de morar também no Streamlit. Rejeitado.
- **Banco online (D1, Supabase…)**: continua o plano B do ADR-0001.

## Consequences

- Token fine-grained com *Contents* e *Actions: Read and write*, só neste repositório, validade de 1 ano (renovar).
- Um clique em "Coletar agora" durante uma Coleta entra na fila (`concurrency: radar`), nunca roda duas ao mesmo tempo.
- O link do Painel nos e-mails vem da variável do repositório `RADAR_LINK_PAINEL` (sobrepõe `link_painel` do config).

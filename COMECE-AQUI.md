# Radar i9+ — comece aqui (Mac)

Agente de IA para Clipping de Comunicação da i9+ Baterias. Busca notícias todo dia, resume com IA gratuita,
avisa por e-mail no mesmo dia o que é importante e mostra tudo num Painel no navegador.

## 1. Onde deixar a pasta

Descompacte o zip e **arraste a pasta `radar-i9` para a sua pasta pessoal** (no Finder: menu *Ir → Início*, a pasta
com o ícone de casinha). Funciona em qualquer lugar, mas o macOS não deixa a coleta **agendada** rodar em
Mesa, Documentos, Downloads ou iCloud.

## 2. Instalar (uma vez só, precisa de internet, 1 a 3 minutos)

1. Abra a pasta e clique com o **botão direito** (ou Control + clique) em **`1 - Instalar.command`** → **Abrir** →
   **Abrir** de novo no aviso. *(O macOS avisa porque o arquivo veio da internet. Só o primeiro precisa disso:
   o instalador libera os outros.)*
2. Uma janela do Terminal abre e instala tudo sozinha (o Python fica só dentro da pasta, não mexe no resto do Mac).
3. No fim ela pergunta se quer abrir o Painel. Aperte **Enter**.

> Se o macOS disser que o arquivo "não pode ser aberto": *Ajustes do Sistema → Privacidade e Segurança*, role até
> o aviso sobre `1 - Instalar.command` e clique em **Abrir Mesmo Assim**.

## 3. Usar

| Arquivo (duplo clique) | O que faz |
|---|---|
| `2 - Abrir o Painel.command` | Abre o Radar no navegador (http://localhost:8501). **Deixe a janela do Terminal aberta** enquanto usa. |
| `3 - Coletar agora.command` | Busca as notícias de agora. O Painel também tem o botão **Coletar agora**. |
| `4 - Agendar coleta diaria.command` | O Mac coleta sozinho todo dia no horário que você escolher (padrão 8h). |
| `scripts/mac/remover-agendamento.command` | Cancela a coleta diária. |

## 4. Ligar a IA (grátis, 2 minutos) — faça antes de apresentar

Sem a chave o Radar coleta, mas não resume nem dá nota às notícias novas.

1. Entre em https://aistudio.google.com/apikey com qualquer conta Google (sem cartão) → **Create API key** → copie.
2. No Painel: aba **Configurações** → **Chave do Gemini** → cole → **Salvar chaves** → **Testar a IA**.
3. Clique em **Coletar agora**. As notícias novas chegam com destaque, eixo, ESG e glossário.

Opcional, para o histórico antigo também ganhar tudo isso: no Terminal, dentro da pasta, `uv run radar reclassificar --limite 150`
(repita em outro dia até acabar; a cota grátis é diária).

## 5. Ligar o e-mail (opcional)

Precisa de um Gmail com verificação em 2 etapas. Crie uma **senha de app** (Conta Google → Segurança →
Verificação em 2 etapas → Senhas de app), e no Painel → **Configurações**, preencha o Gmail e a senha de app,
**Salvar chaves** → **Enviar e-mail de teste**. Troque os destinatários em "Quem recebe e quando".
Sem isso o e-mail fica **simulado** (aparece no log, ninguém recebe) — seguro para demonstrar.

## 6. Entregar para a i9+ usar

- Zipe a pasta **sem** o arquivo `.env` (ele tem as suas chaves) e sem a pasta `.venv`. No Terminal, dentro da pasta pai:
  `zip -r radar-i9.zip radar-i9 -x "radar-i9/.env" "radar-i9/.venv/*" "radar-i9/logs/*"`
- A i9+ repete os passos 1 a 5 com as chaves e o Gmail **dela**.
- Se quiser senha para a aba Configurações, acrescente `SENHA_PAINEL="..."` no `.env`.
- **Para não depender de nenhum computador** (robô no GitHub + Painel na web, de graça): ver `PUBLICAR-NA-NUVEM.md`.
- Quem tiver Windows: ver `README.md`.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| "O Radar ainda não foi instalado" | Rode `1 - Instalar.command` primeiro. |
| Painel não abre no navegador | Abra http://localhost:8501 à mão. A janela do Terminal do passo 3 precisa estar aberta. |
| Coleta mostra `HTTP Error 429` na IA | Cota grátis do minuto/dia acabou. O que faltou fica para a próxima Coleta, nada se perde. |
| Coleta agendada não rodou | Veja `logs/agendador.log`. Pasta em Mesa/Documentos? Mova (passo 1) e agende de novo. |
| Quero ver os testes | Terminal na pasta: `uv run pytest` (67 testes, sem internet). |

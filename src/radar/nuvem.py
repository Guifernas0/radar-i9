"""Painel publicado (Streamlit Community Cloud): o que no PC é arquivo e processo local, na nuvem vira chamada ao GitHub.

- Coletar agora / testar IA / testar e-mail → dispara o workflow `radar.yml` (o robô roda no GitHub Actions).
- Configurações → gravam o `config.toml` no repositório (ver `termos.gravar_no_github`).
- Avaliações (teste de precisão) → gravam `avaliacoes.json` no repositório.
- O Painel nunca escreve no `radar.db` do repositório: o Streamlit Cloud atualiza o app com `git pull`, e um arquivo
  versionado modificado no servidor trava essa atualização. Ele trabalha numa cópia fora do repositório.
"""

import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from radar import db
from radar.termos import gravar_no_github, ler_no_github

API = "https://api.github.com/repos/{repo}"
WORKFLOW = "radar.yml"
AVALIACOES = "avaliacoes.json"
ACOES = {"coleta": "Coleta", "teste-ia": "Teste da IA", "teste-email": "Teste de e-mail"}


# ---------- chamadas ao GitHub ----------

def _pedir(url, token, dados=None, metodo="GET"):
    req = urllib.request.Request(url, data=json.dumps(dados).encode() if dados is not None else None, method=metodo,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Radar i9+"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            corpo = r.read()
            return json.loads(corpo) if corpo else None
    except urllib.error.HTTPError as e:
        dicas = {401: "token inválido ou vencido", 403: "o token não tem a permissão necessária",
                 404: "repositório/workflow não encontrado ou token sem acesso a ele",
                 422: "o workflow radar.yml não aceita essa ação (o arquivo no GitHub está atualizado?)"}
        dica = dicas.get(e.code) or (e.read() or b"").decode("utf-8", "replace")[:150]
        raise RuntimeError(f"GitHub respondeu {e.code}: {dica}") from None


def disparar(repo: str, token: str, acao: str = "coleta", ramo: str = "main") -> None:
    """Liga o robô agora (mesmo efeito do botão *Run workflow* na aba Actions)."""
    if acao not in ACOES:
        raise ValueError(f"ação desconhecida: {acao}")
    _pedir(f"{API.format(repo=repo)}/actions/workflows/{WORKFLOW}/dispatches", token,
           {"ref": ramo, "inputs": {"acao": acao}}, "POST")


def ultimas_execucoes(repo: str, token: str, n: int = 3) -> list[dict]:
    """As últimas rodadas do robô: quando, como terminou e o link do log."""
    r = _pedir(f"{API.format(repo=repo)}/actions/workflows/{WORKFLOW}/runs?per_page={n}", token) or {}
    return [{"quando": x.get("created_at", ""), "status": x.get("status", ""), "resultado": x.get("conclusion"),
             "origem": x.get("event", ""), "link": x.get("html_url", "")} for x in r.get("workflow_runs", [])]


def situacao(execucao: dict) -> str:
    if execucao["status"] in ("queued", "waiting", "pending", "requested"):
        return "na fila"
    if execucao["status"] == "in_progress":
        return "rodando agora"
    return {"success": "concluída", "failure": "falhou", "cancelled": "cancelada"}.get(execucao["resultado"],
                                                                                         execucao["resultado"] or "?")


def editar_config_no_github(repo: str, token: str, editar, mensagem: str) -> None:
    """Lê o config.toml atual do GitHub, aplica a edição (função texto → texto, que valida) e grava por cima."""
    atual, sha = ler_no_github(repo, token)
    gravar_no_github(repo, token, editar(atual), sha, mensagem)


# ---------- banco: cópia de trabalho fora do repositório ----------

def copia_de_trabalho(origem: Path, destino: Path) -> Path:
    """Copia o radar.db do repositório para `destino` sempre que o robô trouxer um banco novo."""
    origem, destino = Path(origem), Path(destino)
    if not origem.exists():
        return origem
    marca = destino.with_suffix(".origem")
    assinatura = f"{origem.stat().st_mtime_ns}:{origem.stat().st_size}"
    if not destino.exists() or not marca.exists() or marca.read_text() != assinatura:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino)
        marca.write_text(assinatura)
        destino.with_suffix(".avaliacoes").unlink(missing_ok=True)  # banco novo: reimportar as avaliações
    return destino


# ---------- avaliações (teste de precisão) ----------

def _chave_av(a):
    return (a["chave"], a["avaliador"])


def importar_avaliacoes(arquivo: Path, banco: Path) -> int:
    """Leva as avaliações do `avaliacoes.json` do repositório para o banco de trabalho do Painel."""
    arquivo = Path(arquivo)
    if not arquivo.exists():
        return 0
    marca = Path(banco).with_suffix(".avaliacoes")  # só reimporta quando o arquivo mudou (o Painel roda a cada clique)
    assinatura = f"{arquivo.stat().st_mtime_ns}:{arquivo.stat().st_size}"
    if marca.exists() and marca.read_text() == assinatura:
        return 0
    lista = json.loads(arquivo.read_text(encoding="utf-8") or "[]")
    for a in lista:
        db.gravar_avaliacao(banco, a["chave"], a["avaliador"], int(a["relevancia"]), a.get("tema"), a["em"])
    marca.write_text(assinatura)
    return len(lista)


def mesclar_avaliacoes(atuais: list[dict], novas: list[dict]) -> list[dict]:
    """Mesma pessoa avaliando a mesma Menção de novo = a nota nova vale."""
    por_chave = {_chave_av(a): a for a in atuais}
    por_chave.update({_chave_av(a): a for a in novas})
    return sorted(por_chave.values(), key=lambda a: (a["avaliador"], a["em"], a["chave"]))


def salvar_avaliacoes_no_github(repo: str, token: str, novas: list[dict], avaliador: str) -> None:
    try:
        texto, sha = ler_no_github(repo, token, AVALIACOES)
        atuais = json.loads(texto or "[]")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        atuais, sha = [], None  # primeira avaliação: o arquivo ainda não existe no repositório
    conteudo = json.dumps(mesclar_avaliacoes(atuais, novas), ensure_ascii=False, indent=1) + "\n"
    gravar_no_github(repo, token, conteudo, sha, f"avaliacoes: {len(novas)} de {avaliador} (pelo Painel)", AVALIACOES)

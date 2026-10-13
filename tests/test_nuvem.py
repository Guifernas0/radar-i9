"""Painel publicado: liga o robô pelo GitHub, grava avaliações no repositório e nunca escreve no radar.db versionado."""

import json
import urllib.error
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from radar import db, nuvem
from test_painel import PAINEL, banco_de_fixture


class Resposta:
    def __init__(self, corpo=b""):
        self.corpo = corpo

    def read(self):
        return self.corpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def github_falso(monkeypatch):
    """Grava cada pedido feito à API do GitHub e devolve respostas prontas."""
    pedidos, respostas = [], {}

    def urlopen(req, timeout=None):
        corpo = json.loads(req.data) if req.data else None
        pedidos.append((req.get_method(), req.full_url, corpo, req.headers))
        r = respostas.get((req.get_method(), req.full_url.split("?")[0]))
        if isinstance(r, Exception):
            raise r
        return Resposta(json.dumps(r).encode() if r is not None else b"")

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return pedidos, respostas


def test_disparar_liga_o_workflow_com_a_acao(github_falso):
    pedidos, _ = github_falso
    nuvem.disparar("org/radar", "tok", "teste-email")
    metodo, url, corpo, headers = pedidos[0]
    assert metodo == "POST"
    assert url == "https://api.github.com/repos/org/radar/actions/workflows/radar.yml/dispatches"
    assert corpo == {"ref": "main", "inputs": {"acao": "teste-email"}}
    assert headers["Authorization"] == "Bearer tok"


def test_disparar_recusa_acao_desconhecida(github_falso):
    with pytest.raises(ValueError):
        nuvem.disparar("org/radar", "tok", "apagar-tudo")
    assert github_falso[0] == []


def test_erro_do_github_vira_mensagem_legivel(github_falso):
    _, respostas = github_falso
    url = "https://api.github.com/repos/org/radar/actions/workflows/radar.yml/dispatches"
    respostas[("POST", url)] = urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
    with pytest.raises(RuntimeError, match="403.*permissão"):
        nuvem.disparar("org/radar", "tok")


def test_ultimas_execucoes_e_situacao(github_falso):
    _, respostas = github_falso
    respostas[("GET", "https://api.github.com/repos/org/radar/actions/workflows/radar.yml/runs")] = {"workflow_runs": [
        {"created_at": "2026-10-13T11:00:00Z", "status": "in_progress", "conclusion": None, "event": "workflow_dispatch", "html_url": "u1"},
        {"created_at": "2026-10-12T11:00:00Z", "status": "completed", "conclusion": "success", "event": "schedule", "html_url": "u2"},
    ]}
    execs = nuvem.ultimas_execucoes("org/radar", "tok")
    assert [nuvem.situacao(x) for x in execs] == ["rodando agora", "concluída"]
    assert execs[1]["link"] == "u2"


def test_copia_de_trabalho_renova_so_quando_o_robo_traz_banco_novo(tmp_path):
    origem = banco_de_fixture(tmp_path)
    destino = tmp_path / "trabalho" / "radar.db"
    assert nuvem.copia_de_trabalho(origem, destino) == destino
    chave = db.listar_mencoes(destino)[0].chave
    db.gravar_avaliacao(destino, chave, "Ana", 7, None, "2026-10-13")  # escrita do Painel vai só na cópia
    assert db.listar_avaliacoes(origem) == []
    antes = destino.read_bytes()
    nuvem.copia_de_trabalho(origem, destino)
    assert destino.read_bytes() == antes  # mesma origem: não recopia (não perde o que o Painel gravou)
    import os
    os.utime(origem, ns=(origem.stat().st_atime_ns, origem.stat().st_mtime_ns + 10**9))
    nuvem.copia_de_trabalho(origem, destino)
    assert destino.read_bytes() == origem.read_bytes()  # robô commitou banco novo: recopia


def test_copia_de_trabalho_sem_banco_devolve_a_origem(tmp_path):
    assert nuvem.copia_de_trabalho(tmp_path / "nao.db", tmp_path / "t" / "radar.db") == tmp_path / "nao.db"


def test_importar_avaliacoes_e_reimporta_so_se_mudar(tmp_path):
    banco = banco_de_fixture(tmp_path)
    chave = db.listar_mencoes(banco)[0].chave
    arquivo = tmp_path / "avaliacoes.json"
    arquivo.write_text(json.dumps([{"chave": chave, "avaliador": "Ana", "relevancia": 9, "tema": None, "em": "2026-10-13"}]))
    assert nuvem.importar_avaliacoes(arquivo, banco) == 1
    assert nuvem.importar_avaliacoes(arquivo, banco) == 0  # nada mudou: não reescreve o banco a cada clique
    assert db.listar_avaliacoes(banco)[0]["nota_humana"] == 9


def test_mesclar_avaliacoes_nota_nova_vence():
    a = [{"chave": "k1", "avaliador": "Ana", "relevancia": 3, "tema": None, "em": "2026-10-01"}]
    b = [{"chave": "k1", "avaliador": "Ana", "relevancia": 8, "tema": None, "em": "2026-10-13"},
         {"chave": "k1", "avaliador": "Bia", "relevancia": 5, "tema": None, "em": "2026-10-13"}]
    m = nuvem.mesclar_avaliacoes(a, b)
    assert [(x["avaliador"], x["relevancia"]) for x in m] == [("Ana", 8), ("Bia", 5)]


def test_salvar_avaliacoes_cria_o_arquivo_no_repositorio(github_falso):
    pedidos, respostas = github_falso
    url = "https://api.github.com/repos/org/radar/contents/avaliacoes.json"
    respostas[("GET", url)] = urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    respostas[("PUT", url)] = {"content": {"sha": "novo"}}  # o GitHub responde o arquivo criado
    nova = {"chave": "k1", "avaliador": "Ana", "relevancia": 8, "tema": "baterias", "em": "2026-10-13"}
    nuvem.salvar_avaliacoes_no_github("org/radar", "tok", [nova], "Ana")
    metodo, _, corpo, _ = pedidos[-1]
    assert metodo == "PUT" and "sha" not in corpo
    import base64
    assert json.loads(base64.b64decode(corpo["content"])) == [nova]


def _painel_na_nuvem(tmp_path, monkeypatch, segredos=None):
    banco = banco_de_fixture(tmp_path)
    monkeypatch.setenv("RADAR_DB", str(banco))
    monkeypatch.setenv("RADAR_SOMENTE_LEITURA", "1")  # = rodando no Streamlit Cloud
    monkeypatch.setenv("RADAR_PASTA_TRABALHO", str(tmp_path / "trabalho"))
    app = AppTest.from_file(str(PAINEL), default_timeout=30)
    for k, v in (segredos or {}).items():
        app.secrets[k] = v
    return banco, app.run()


def test_painel_na_nuvem_sem_segredos_fica_so_leitura_e_nao_toca_no_banco(tmp_path, monkeypatch):
    banco, app = _painel_na_nuvem(tmp_path, monkeypatch)
    antes = banco.read_bytes()
    assert not app.exception
    assert not [b for b in app.button if b.label == "Coletar agora"]
    assert any("somente leitura" in i.value for i in app.info)
    assert banco.read_bytes() == antes


def test_painel_na_nuvem_pede_senha_e_depois_mostra_coletar_agora(tmp_path, monkeypatch, github_falso):
    _, respostas = github_falso
    respostas[("GET", "https://api.github.com/repos/org/radar/actions/workflows/radar.yml/runs")] = {"workflow_runs": []}
    _, app = _painel_na_nuvem(tmp_path, monkeypatch, {"GITHUB_TOKEN": "tok", "SENHA_PAINEL": "segredo", "RADAR_REPO": "org/radar"})
    assert not app.exception
    assert not [b for b in app.button if b.label == "Coletar agora"]
    app.text_input(key="senha_lateral").set_value("errada").run()
    assert any("Senha incorreta" in e.value for e in app.error)
    app.text_input(key="senha_lateral").set_value("segredo").run()
    assert not app.exception
    botao = [b for b in app.button if b.label == "Coletar agora"]
    assert botao
    botao[0].click().run()
    pedidos = github_falso[0]
    assert any(m == "POST" and u.endswith("/dispatches") and c["inputs"]["acao"] == "coleta" for m, u, c, _ in pedidos)

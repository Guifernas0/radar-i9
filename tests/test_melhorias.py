"""Melhorias de 09/2026: eixos fixos, ESG, "leia hoje", assunto padrão, filtro de feed, rótulo, migração do histórico."""

import json
import sqlite3
from datetime import date

from radar import db as dbm
from radar import eixos
from radar.coleta import Noticia, analisar_pendentes, carregar_config, coletar, e_de_fonte_conhecida, passa_no_filtro
from radar.db import listar_avaliacoes, gravar_avaliacao, listar_mencoes
from test_coleta import CONFIG_TOML, HOJE, MARCA1, N3, FonteFalsa, IAFalsa, RemetenteFalso

TOPO = '''projeto = "P2 - Agente de IA para Clipping de Comunicação"
fontes_conhecidas = ["Valor", "gov.br"]
'''
EXTRA = '''
[alerta]
relevancia_minima = 8
max_itens = 2

[[feeds]]
nome = "Câmara"
url = "https://camara/rss"
filtro = ["bateria", "lítio"]
'''


def cfg(tmp_path, extra=EXTRA):
    p = tmp_path / "config.toml"
    p.write_text(TOPO + CONFIG_TOML + extra, encoding="utf-8")
    return carregar_config(p)


class IANota:
    def __init__(self, notas):
        self.notas = notas

    def analisar(self, titulo, fonte, trecho=""):
        return {"resumo": "r", "relevancia": self.notas.get(titulo, 3), "tema": "mercado", "sentimento": "positivo",
                "esg": "ambiental", "destaque": f"dado de {titulo}", "termos_tecnicos": [{"termo": "BESS", "explicacao": "x"}]}


class FeedsFalsos:
    def __init__(self, noticias):
        self.noticias = noticias

    def ler(self, url, nome):
        return self.noticias


def test_eixos_normalizam_temas_livres_antigos():
    assert eixos.normalizar_tema("baterias") == "tecnologia"
    assert eixos.normalizar_tema("Regulação") == "legislação"
    assert eixos.normalizar_tema("economia circular") == "esg"
    assert eixos.normalizar_tema("concorrência") == "mercado"
    assert eixos.normalizar_tema("LEGISLACAO") == "legislação"
    assert eixos.normalizar_tema("") == "sem classificação"
    assert eixos.normalizar_esg("G") == "governança" and eixos.normalizar_esg("amb") == "ambiental"
    assert eixos.normalizar_esg("qualquer") == "nenhum"


def test_esg_por_regra():
    assert eixos.esg_por_regra("Reciclagem de baterias de segunda vida cresce") == "ambiental"
    assert eixos.esg_por_regra("Projeto de lei cria regulamentação para baterias") == "governança"
    assert eixos.esg_por_regra("Preço do lítio sobe") == "nenhum"


def test_campos_novos_da_ia_vao_para_o_banco(tmp_path):
    fonte = FonteFalsa({("baterias de segunda vida", "pt"): [N3]})
    coletar(cfg(tmp_path), fonte, IANota({}), RemetenteFalso(), HOJE, tmp_path / "radar.db")
    m = listar_mencoes(tmp_path / "radar.db")[0]
    assert (m.esg, m.destaque, m.origem) == ("ambiental", f"dado de {N3.titulo}", "ia")
    assert json.loads(m.termos_tecnicos) == [{"termo": "BESS", "explicacao": "x"}]


def test_leia_hoje_dispara_alerta_por_relevancia_com_assunto_padrao(tmp_path):
    vital = Noticia("Senado aprova lei das baterias", "https://ex.com/lei", "Agência Senado", "2026-08-25")
    fonte = FonteFalsa({("baterias de segunda vida", "pt"): [vital, N3]})
    rem = RemetenteFalso()
    coletar(cfg(tmp_path), fonte, IANota({vital.titulo: 9}), rem, HOJE, tmp_path / "radar.db")

    alertas = [e for e in rem.enviados if "leia hoje" in e[1]]
    assert len(alertas) == 1
    _, assunto, texto, html = alertas[0]
    assert assunto.startswith("P2 - Agente de IA para Clipping de Comunicação - Alerta leia hoje: 1 notícia vital")
    assert vital.titulo in texto and N3.titulo not in texto and f"dado de {vital.titulo}" in html
    assert all(e[1].startswith("P2 - Agente de IA") for e in rem.enviados)  # Digest também


def test_leia_hoje_nao_reenvia_e_nao_alerta_historico_antigo(tmp_path):
    vital = Noticia("Senado aprova lei das baterias", "https://ex.com/lei", "Agência Senado", "2026-08-25")
    fonte = FonteFalsa({("baterias de segunda vida", "pt"): [vital]})
    rem = RemetenteFalso()
    c, banco = cfg(tmp_path), tmp_path / "radar.db"
    coletar(c, fonte, IANota({vital.titulo: 9}), rem, HOJE, banco)
    coletar(c, fonte, IANota({vital.titulo: 9}), rem, HOJE, banco)
    coletar(c, FonteFalsa({}), IANota({}), rem, date(2026, 9, 20), banco)  # semanas depois: não realerta
    assert len([e for e in rem.enviados if "leia hoje" in e[1]]) == 1


def test_marca_e_leia_hoje_vao_no_mesmo_email(tmp_path):
    vital = Noticia("Senado aprova lei das baterias", "https://ex.com/lei", "Agência Senado", "2026-08-25")
    fonte = FonteFalsa({("InoveMais", "pt"): [MARCA1], ("baterias de segunda vida", "pt"): [vital]})
    rem = RemetenteFalso()
    coletar(cfg(tmp_path), fonte, IANota({vital.titulo: 10}), rem, HOJE, tmp_path / "radar.db")
    alertas = [e for e in rem.enviados if "Alerta" in e[1]]
    assert len(alertas) == 1 and "Alerta de marca: 1 menção" in alertas[0][1] and "leia hoje: 1" in alertas[0][1]
    assert MARCA1.titulo in alertas[0][2] and vital.titulo in alertas[0][2]


def test_feed_com_filtro_so_guarda_o_que_cita_as_palavras(tmp_path):
    sim = Noticia("Comissão debate reciclagem de baterias", "https://camara/1", "Câmara", "2026-08-25")
    nao = Noticia("Comissão debate merenda escolar", "https://camara/2", "Câmara", "2026-08-25")
    lit = Noticia("Audiência sobre mineração", "https://camara/3", "Câmara", "2026-08-25", trecho="reservas de lítio no Vale")
    coletar(cfg(tmp_path), FonteFalsa({}), IAFalsa(), RemetenteFalso(), HOJE, tmp_path / "radar.db", feeds=FeedsFalsos([sim, nao, lit]))
    assert sorted(m.link for m in listar_mencoes(tmp_path / "radar.db")) == ["https://camara/1", "https://camara/3"]
    assert passa_no_filtro(nao, [])


def test_rotulo_aparece_como_termo_da_mencao(tmp_path):
    extra = '[[termos]]\ntexto = "batteries site:weforum.org"\nrotulo = "Fórum Econômico Mundial"\nidiomas = ["en"]\n'
    p = tmp_path / "config.toml"
    p.write_text(CONFIG_TOML + extra, encoding="utf-8")
    c = carregar_config(p)
    n = Noticia("Batteries and the energy transition", "https://weforum.org/x", "WEF", "2026-08-25")
    coletar(c, FonteFalsa({("batteries site:weforum.org", "en"): [n]}), IAFalsa(), RemetenteFalso(), HOJE, tmp_path / "radar.db")
    assert listar_mencoes(tmp_path / "radar.db")[0].termo == "Fórum Econômico Mundial"


def test_fonte_conhecida_por_nome_ou_dominio(tmp_path):
    c = cfg(tmp_path)
    assert e_de_fonte_conhecida(c, "Valor Econômico", "https://news.google.com/x")
    assert e_de_fonte_conhecida(c, "Ministério", "https://www.mme.gov.br/noticia")
    assert not e_de_fonte_conhecida(c, "Blog qualquer", "https://blog.com.br/x")


def test_ia_para_depois_de_5_falhas_seguidas_e_respeita_maximo(tmp_path):
    class IAQueFalha:
        chamadas = 0

        def analisar(self, *a):
            IAQueFalha.chamadas += 1
            raise RuntimeError("sem chave")

    muitas = [Noticia(f"N{i}", f"https://ex.com/{i}", "F", "2026-08-25") for i in range(20)]
    c = cfg(tmp_path)
    coletar(c, FonteFalsa({("baterias de segunda vida", "pt"): muitas}), IAQueFalha(), RemetenteFalso(), HOJE, tmp_path / "radar.db")
    assert IAQueFalha.chamadas == 5

    con = dbm.abrir(tmp_path / "radar.db")
    c2 = carregar_config(tmp_path / "config.toml").__class__(**{**c.__dict__, "ia": {"max_por_coleta": 3}})
    esperas = []
    ok, _ = analisar_pendentes(c2, IAFalsa(), con, log=lambda *_: None, esperar=esperas.append)
    assert ok == 3 and esperas == []


def test_banco_antigo_migra_tema_para_eixo_e_ganha_esg_por_regra(tmp_path):
    banco = tmp_path / "antigo.db"
    con = sqlite3.connect(banco)
    con.executescript("""CREATE TABLE mencoes (chave TEXT PRIMARY KEY, titulo TEXT NOT NULL, link TEXT NOT NULL, fonte TEXT,
        data TEXT, idioma TEXT, termo TEXT, resumo TEXT, relevancia INTEGER, tema TEXT, sentimento TEXT,
        marca INTEGER NOT NULL DEFAULT 0, coletada_em TEXT NOT NULL, reprocessar INTEGER NOT NULL DEFAULT 1);
        INSERT INTO mencoes VALUES ('a','Reciclagem de baterias cresce','l1','F','2026-08-01','pt','t','r',7,'baterias','positivo',0,'2026-08-01',0);
        INSERT INTO mencoes VALUES ('b','Pendente','l2','F','2026-08-01','pt','t',NULL,NULL,NULL,NULL,0,'2026-08-01',1);""")
    con.commit()
    con.close()

    ms = {m.chave: m for m in listar_mencoes(banco)}
    assert (ms["a"].tema, ms["a"].esg, ms["a"].origem) == ("tecnologia", "ambiental", "regra")
    assert (ms["b"].esg, ms["b"].reprocessar) == (None, True)  # pendente vai à IA, não à regra

    con = dbm.abrir(banco)
    assert dbm.marcar_para_reclassificar(con) == 1
    con.commit()
    con.close()
    assert {m.chave for m in listar_mencoes(banco) if m.reprocessar} == {"a", "b"}


def test_avaliacao_humana_fica_ao_lado_da_nota_da_ia(tmp_path):
    fonte = FonteFalsa({("baterias de segunda vida", "pt"): [N3]})
    banco = tmp_path / "radar.db"
    coletar(cfg(tmp_path), fonte, IANota({N3.titulo: 6}), RemetenteFalso(), HOJE, banco)
    chave = listar_mencoes(banco)[0].chave
    gravar_avaliacao(banco, chave, "Tiago", 8, "mercado", "2026-09-29")
    gravar_avaliacao(banco, chave, "Tiago", 7, "mercado", "2026-09-29")  # regravar substitui
    (a,) = listar_avaliacoes(banco)
    assert (a["nota_humana"], a["nota_ia"], a["tema_humano"], a["tema_ia"]) == (7, 6, "mercado", "mercado")


def test_sem_chave_de_ia_pula_a_analise_sem_marcar_falha(tmp_path):
    from radar.cli import _IASemChave
    linhas = []
    coletar(cfg(tmp_path), FonteFalsa({("baterias de segunda vida", "pt"): [N3]}), _IASemChave(), RemetenteFalso(), HOJE,
            tmp_path / "radar.db", log=linhas.append)
    m = listar_mencoes(tmp_path / "radar.db")[0]
    assert m.reprocessar and m.tema is None and any("sem chave" in l for l in linhas)

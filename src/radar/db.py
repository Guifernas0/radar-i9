"""Histórico: SQLite num arquivo. Nada é apagado, nunca."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from radar import eixos

SCHEMA = """
CREATE TABLE IF NOT EXISTS mencoes (
  chave TEXT PRIMARY KEY,
  titulo TEXT NOT NULL,
  link TEXT NOT NULL,
  fonte TEXT,
  data TEXT,
  idioma TEXT,
  termo TEXT,
  resumo TEXT,
  relevancia INTEGER,
  tema TEXT,
  sentimento TEXT,
  marca INTEGER NOT NULL DEFAULT 0,
  coletada_em TEXT NOT NULL,
  reprocessar INTEGER NOT NULL DEFAULT 1,
  trecho TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS coletas (
  data TEXT PRIMARY KEY,
  novas INTEGER NOT NULL,
  ignoradas INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS avaliacoes (
  chave TEXT NOT NULL,
  avaliador TEXT NOT NULL,
  relevancia INTEGER NOT NULL,
  tema TEXT,
  em TEXT NOT NULL,
  PRIMARY KEY (chave, avaliador)
);
CREATE TABLE IF NOT EXISTS envios (
  id INTEGER PRIMARY KEY,
  tipo TEXT NOT NULL,
  data TEXT NOT NULL,
  quantidade INTEGER NOT NULL,
  chaves TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Mencao:
    chave: str
    titulo: str
    link: str
    fonte: str
    data: str
    idioma: str
    termo: str
    resumo: str | None
    relevancia: int | None
    tema: str | None
    sentimento: str | None
    marca: bool
    coletada_em: str
    reprocessar: bool
    trecho: str = ""
    esg: str | None = None
    destaque: str = ""
    termos_tecnicos: str = "[]"  # JSON: [{"termo", "explicacao"}]
    origem: str | None = None    # "ia" | "regra" (histórico anterior aos eixos fixos, classificado por palavras)


COLUNAS_NOVAS = {  # coluna → definição; entram sozinhas em bancos antigos
    "trecho": "TEXT NOT NULL DEFAULT ''",
    "esg": "TEXT",
    "destaque": "TEXT NOT NULL DEFAULT ''",
    "termos_tecnicos": "TEXT NOT NULL DEFAULT '[]'",
    "origem": "TEXT",
}
VERSAO = 2  # 2 = eixos fixos de tema + ESG


def abrir(caminho: Path) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    existentes = {r[1] for r in con.execute("PRAGMA table_info(mencoes)")}
    for col, definicao in COLUNAS_NOVAS.items():
        if col not in existentes:
            con.execute(f"ALTER TABLE mencoes ADD COLUMN {col} {definicao}")
    if con.execute("PRAGMA user_version").fetchone()[0] < VERSAO:
        _migrar_para_eixos(con)
        con.execute(f"PRAGMA user_version = {VERSAO}")
    con.commit()
    return con


def _migrar_para_eixos(con):
    """Uma vez só: tema livre antigo → eixo fixo; ESG por regra de palavras (origem = "regra").
    `radar reclassificar` refaz essas com a IA quando houver cota."""
    for r in con.execute("SELECT chave, titulo, resumo, trecho, tema, reprocessar FROM mencoes WHERE esg IS NULL").fetchall():
        if r["reprocessar"]:
            continue  # vai à IA na próxima Coleta de qualquer jeito
        con.execute("UPDATE mencoes SET tema = ?, esg = ?, origem = 'regra' WHERE chave = ?",
                    (eixos.normalizar_tema(r["tema"]), eixos.esg_por_regra(r["titulo"], r["resumo"], r["trecho"]), r["chave"]))


def inserir_mencao(con, chave, noticia, idioma, termo, coletada_em) -> bool:
    """True se entrou; False se já existia (dedupe pela chave do link e, entre Fontes, pelo título)."""
    trecho = getattr(noticia, "trecho", "") or ""
    igual = con.execute("SELECT chave, trecho FROM mencoes WHERE lower(titulo) = lower(?) LIMIT 1", (noticia.titulo,)).fetchone()
    if igual:
        if trecho and not igual["trecho"]:  # a outra Fonte trouxe o corpo: enriquece e manda de volta à IA
            con.execute("UPDATE mencoes SET trecho = ?, reprocessar = 1 WHERE chave = ?", (trecho, igual["chave"]))
        return False
    cur = con.execute(
        "INSERT OR IGNORE INTO mencoes (chave, titulo, link, fonte, data, idioma, termo, coletada_em, trecho)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (chave, noticia.titulo, noticia.link, noticia.fonte, noticia.data, idioma, termo, coletada_em, trecho),
    )
    return cur.rowcount == 1


def _mencao(row) -> Mencao:
    d = dict(row)
    d["marca"] = bool(d["marca"])
    d["reprocessar"] = bool(d["reprocessar"])
    return Mencao(**d)


def listar_mencoes(caminho: Path) -> list[Mencao]:
    con = abrir(caminho)
    try:
        return [_mencao(r) for r in con.execute("SELECT * FROM mencoes ORDER BY coletada_em DESC, data DESC")]
    finally:
        con.close()


def pendentes_de_ia(con) -> list[Mencao]:
    """Mais novas primeiro: se a cota acabar no meio, o que chegou hoje já está analisado."""
    return [_mencao(r) for r in con.execute("SELECT * FROM mencoes WHERE reprocessar = 1 ORDER BY coletada_em DESC, data DESC")]


def marcar_para_reclassificar(con, so_regra=True, limite=None) -> int:
    """Manda de volta à IA (as classificadas por regra, ou todas). Mais recentes primeiro."""
    onde = "WHERE origem = 'regra'" if so_regra else ""
    lim = f"LIMIT {int(limite)}" if limite else ""
    chaves = [r[0] for r in con.execute(f"SELECT chave FROM mencoes {onde} ORDER BY data DESC {lim}")]
    con.executemany("UPDATE mencoes SET reprocessar = 1 WHERE chave = ?", [(c,) for c in chaves])
    return len(chaves)


def gravar_analise(con, chave, resumo, relevancia, tema, sentimento, esg=None, destaque="", termos_tecnicos=()):
    con.execute(
        "UPDATE mencoes SET resumo=?, relevancia=?, tema=?, sentimento=?, esg=?, destaque=?, termos_tecnicos=?,"
        " origem='ia', reprocessar=0 WHERE chave=?",
        (resumo, relevancia, tema, sentimento, esg, destaque or "", json.dumps(list(termos_tecnicos or []), ensure_ascii=False), chave),
    )


def gravar_falha_de_ia(con, chave, titulo):
    """Guarda mesmo assim: título vira resumo, sem nota, continua marcada para reprocessar."""
    con.execute(
        "UPDATE mencoes SET resumo=COALESCE(resumo, ?), tema='sem classificação', reprocessar=1 WHERE chave=?",
        (titulo, chave),
    )


def gravar_marca(con, chave, marca: bool):
    con.execute("UPDATE mencoes SET marca=? WHERE chave=?", (int(marca), chave))


def todas(con) -> list[Mencao]:
    return [_mencao(r) for r in con.execute("SELECT * FROM mencoes")]


def por_chaves(con, chaves) -> list[Mencao]:
    if not chaves:
        return []
    q = ",".join("?" * len(chaves))
    return [_mencao(r) for r in con.execute(f"SELECT * FROM mencoes WHERE chave IN ({q})", list(chaves))]


def vitais_recentes(con, minimo: int, desde: str) -> list[Mencao]:
    """"Leia hoje": Relevância >= mínimo, coletadas a partir de `desde`, que não sejam de marca (essas já têm Alerta)."""
    return [_mencao(r) for r in con.execute(
        "SELECT * FROM mencoes WHERE marca = 0 AND relevancia >= ? AND coletada_em >= ? ORDER BY relevancia DESC, data DESC",
        (minimo, desde))]


def mencoes_de_marca(con) -> list[Mencao]:
    return [_mencao(r) for r in con.execute("SELECT * FROM mencoes WHERE marca = 1 ORDER BY data DESC")]


def sem_envio(con, tipo, mencoes) -> list[Mencao]:
    """Menções que ainda não constam em nenhum envio desse tipo."""
    ja = set()
    for (chaves,) in con.execute("SELECT chaves FROM envios WHERE tipo = ?", (tipo,)):
        ja.update(chaves.split(","))
    return [m for m in mencoes if m.chave not in ja]


def registrar_envio(con, tipo, data, mencoes):
    con.execute(
        "INSERT INTO envios (tipo, data, quantidade, chaves) VALUES (?, ?, ?, ?)",
        (tipo, data, len(mencoes), ",".join(m.chave for m in mencoes)),
    )


def ultimo_envio(con, tipo) -> str | None:
    r = con.execute("SELECT MAX(data) FROM envios WHERE tipo = ?", (tipo,)).fetchone()
    return r[0] if r else None


def todas_ordenadas_para_digest(con) -> list[Mencao]:
    """Marca primeiro, depois Relevância decrescente (sem nota por último), depois data."""
    return [_mencao(r) for r in con.execute(
        "SELECT * FROM mencoes ORDER BY marca DESC, relevancia IS NULL, relevancia DESC, data DESC")]


def registrar_coleta(con, data, novas, ignoradas):
    con.execute("INSERT OR REPLACE INTO coletas (data, novas, ignoradas) VALUES (?, ?, ?)", (data, novas, ignoradas))


def ultima_coleta(caminho: Path) -> str | None:
    con = abrir(caminho)
    try:
        return con.execute("SELECT MAX(data) FROM coletas").fetchone()[0]
    finally:
        con.close()


def ultimo_envio_por_tipo(caminho: Path, tipo) -> str | None:
    con = abrir(caminho)
    try:
        return ultimo_envio(con, tipo)
    finally:
        con.close()


# ---------- Avaliação humana x IA (teste de precisão, Cronograma C19) ----------

def gravar_avaliacao(caminho: Path, chave: str, avaliador: str, relevancia: int, tema: str | None, em: str):
    con = abrir(caminho)
    try:
        con.execute("INSERT OR REPLACE INTO avaliacoes (chave, avaliador, relevancia, tema, em) VALUES (?, ?, ?, ?, ?)",
                    (chave, avaliador.strip(), int(relevancia), tema, em))
        con.commit()
    finally:
        con.close()


def listar_avaliacoes(caminho: Path) -> list[dict]:
    """Cada avaliação humana ao lado do que a IA disse."""
    con = abrir(caminho)
    try:
        return [dict(r) for r in con.execute(
            "SELECT a.chave, a.avaliador, a.relevancia AS nota_humana, a.tema AS tema_humano, a.em,"
            " m.relevancia AS nota_ia, m.tema AS tema_ia, m.titulo FROM avaliacoes a JOIN mencoes m USING (chave)")]
    finally:
        con.close()

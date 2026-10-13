"""Painel do Radar i9+ — `uv run streamlit run painel.py` (no Mac: duplo clique em "2 - Abrir o Painel.command").

No PC: lê o radar.db local, tem botão "Coletar agora" e aba Configurações (chaves, e-mails, Termos, critério da IA).
Na nuvem (Streamlit Community Cloud), com GITHUB_TOKEN e SENHA_PAINEL nos Secrets do app, faz o mesmo pelo GitHub:
"Coletar agora" liga o robô no GitHub Actions, Configurações e avaliações gravam no repositório (ver radar/nuvem.py).
Sem esses Secrets, o Painel publicado fica só leitura.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))  # Streamlit Cloud instala só o requirements.txt; o pacote radar vive em src/

from radar import ajustes, nuvem  # noqa: E402
from radar.cli import ler_dotenv  # noqa: E402
from radar.coleta import carregar_config, e_de_fonte_conhecida  # noqa: E402
from radar.db import gravar_avaliacao, listar_avaliacoes, listar_mencoes, ultima_coleta, ultimo_envio_por_tipo  # noqa: E402
from radar.eixos import ESG, SEM, TEMAS  # noqa: E402
from radar.termos import adicionar_termo, remover_termo  # noqa: E402

DB = Path(os.environ.get("RADAR_DB", RAIZ / "radar.db"))
CONFIG = RAIZ / "config.toml"
ENV = RAIZ / ".env"
NUVEM = str(RAIZ).startswith("/mount/src") or bool(os.environ.get("RADAR_SOMENTE_LEITURA"))
cfg = carregar_config(CONFIG)
MINIMO = cfg.minimo_vital

# Paleta i9+ (validada p/ daltonismo sobre o fundo escuro): azul = setor, vermelho = marca, verde = positivo.
AZUL, VERMELHO, VERDE, CINZA, AMBAR = "#4592ff", "#f5121c", "#22a35e", "#8a8f99", "#e0a526"
COR_SENT = {"positivo": VERDE, "neutro": CINZA, "negativo": VERMELHO}
COR_ESG = {"ambiental": VERDE, "social": AMBAR, "governança": AZUL}
_SVG = ("<svg width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' "
        "stroke-linecap='round' stroke-linejoin='round' style='vertical-align:-1px;margin-right:.3rem'>{}</svg>")
ICONE = {
    "positivo": _SVG.format("<path d='M20 6 9 17l-5-5'/>"),
    "neutro": _SVG.format("<path d='M5 12h14'/>"),
    "negativo": _SVG.format("<path d='M12 5v9'/><path d='M12 18h.01'/>"),
    "sem análise": _SVG.format("<circle cx='12' cy='12' r='8'/>"),
    "marca": _SVG.format("<path d='M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9'/><path d='M10 21h4'/>"),
    "vital": _SVG.format("<path d='M13 2 3 14h9l-1 8 10-12h-9l1-8z'/>"),
    "escudo": _SVG.format("<path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/>"),
}
PERIODOS = {"7 dias": 7, "30 dias": 30, "90 dias": 90, "Tudo": None}

LOGO = str(RAIZ / "static" / "logo-i9-fundo.png")  # logo branco sobre chip escuro: legível no tema claro e no escuro
st.set_page_config(page_title=cfg.nome, page_icon=LOGO, layout="wide")
st.logo(LOGO, size="large", link="https://inovemais.tec.br")
st.markdown(
    f"""<style>
    .block-container {{ padding-top: 1.2rem; }}
    [data-testid="stMetricLabel"] {{ font-size: .8rem; opacity: .75; }}
    .pill {{ display:inline-block; padding:.1rem .55rem; border-radius:999px; font-size:.72rem; font-weight:600;
             margin:0 .3rem .2rem 0; color:#fff; }}
    .pill.neutra {{ background: rgba(128,136,150,.22); color: inherit; }}
    .meta {{ opacity:.75; font-size:.8rem; margin:.45rem 0 0; }}
    .resumo {{ opacity:.9; font-size:.88rem; line-height:1.45; }}
    .titulo a {{ color:inherit; text-decoration:none; font-weight:600; font-size:1rem; }}
    .titulo a:hover {{ color:{AZUL}; }}
    .destaque {{ font-size:1.18rem; line-height:1.3; font-weight:700; margin:.35rem 0 .45rem; }}
    .destaque-fonte {{ font-size:.85rem; opacity:.8; }}
    .destaque-fonte a {{ color:inherit; }}
    .faixa {{ height:6px; border-radius:3px; background:linear-gradient(90deg,{VERMELHO},{AZUL}); margin-bottom:.6rem; }}
    .hoje {{ border-left:4px solid {AZUL}; padding:.1rem 0 .1rem .8rem; margin:.4rem 0 .6rem; }}
    .hoje h3 {{ margin:0; font-size:1.35rem; }}
    .hoje p {{ margin:.1rem 0 0; opacity:.75; font-size:.88rem; }}
    </style><div class="faixa"></div>""",
    unsafe_allow_html=True)


def br(iso):
    return "/".join(reversed(iso.split("-"))) if iso and len(iso) == 10 else (iso or "—")


def segredo(nome):
    try:
        return st.secrets.get(nome) or os.environ.get(nome)
    except Exception:  # sem arquivo de secrets (rodando no PC)
        return os.environ.get(nome) or ler_dotenv(ENV).get(nome)


REPO = segredo("RADAR_REPO") or "tiagoalgauer/radar-i9"
RAMO = segredo("RADAR_RAMO") or "main"
TOKEN = segredo("GITHUB_TOKEN")
SENHA = segredo("SENHA_PAINEL") or segredo("SENHA_TERMOS")  # SENHA_TERMOS = nome antigo, continua valendo
GITHUB = bool(TOKEN and SENHA)  # o Painel grava no GitHub (Termos; na nuvem também Coletar agora, configurações, avaliações)
BRT = timezone(timedelta(hours=-3))

if NUVEM:  # nunca escrever no radar.db do repositório: travaria o `git pull` com que o Streamlit Cloud atualiza o app
    PASTA = Path(os.environ.get("RADAR_PASTA_TRABALHO") or Path(tempfile.gettempdir()) / "radar-painel")
    DB = nuvem.copia_de_trabalho(DB, PASTA / "radar.db")
    try:
        nuvem.importar_avaliacoes(RAIZ / nuvem.AVALIACOES, DB)
    except Exception as e:  # avaliação é extra: nunca derruba o Painel
        print(f"avaliacoes.json ignorado: {e}")


def liberado():
    """Pode mudar coisas? No PC sem senha, sim. Na nuvem, só quem digitou a senha da equipe nesta sessão."""
    if not SENHA:
        return not NUVEM
    return bool(st.session_state.get("senha_ok"))


def campo_senha(chave, rotulo="Senha da equipe"):
    digitada = st.text_input(rotulo, type="password", key=chave)
    if digitada and digitada == SENHA:
        st.session_state["senha_ok"] = True
        st.rerun()
    elif digitada:
        st.error("Senha incorreta.")


def hora_br(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(BRT).strftime("%d/%m %H:%M")
    except (ValueError, AttributeError):
        return iso or "—"


@st.cache_data(ttl=15, show_spinner=False)
def _execucoes(repo, token):
    return nuvem.ultimas_execucoes(repo, token)


def mostrar_execucoes():
    """Últimas rodadas do robô no GitHub Actions, com link para o log."""
    try:
        execs = _execucoes(REPO, TOKEN)
    except Exception as e:
        st.caption(f"Não consegui ler as rodadas do robô: {e}")
        return
    if not execs:
        st.caption("O robô ainda não rodou neste repositório.")
        return
    st.caption("**Últimas rodadas do robô**  \n" + "  \n".join(
        f"{hora_br(x['quando'])} · {nuvem.situacao(x)} · [log]({x['link']})" for x in execs))
    if any(x["status"] != "completed" for x in execs):
        st.button("Atualizar", icon=":material/refresh:", key="atualizar_execucoes", on_click=_execucoes.clear)


def ligar_robo(acao):
    try:
        nuvem.disparar(REPO, TOKEN, acao, RAMO)
        _execucoes.clear()
        st.toast(f"{nuvem.ACOES[acao]} iniciada no GitHub. Leva de 2 a 8 min.", icon=":material/rocket_launch:")
        return True
    except Exception as e:
        st.error(f"Não consegui ligar o robô: {e}")
        return False


mencoes = listar_mencoes(DB) if DB.exists() else []
ultima = ultima_coleta(DB) if DB.exists() else None
ultimo_digest = ultimo_envio_por_tipo(DB, "digest") if DB.exists() else None
proximo = br((date.fromisoformat(ultimo_digest) + timedelta(days=cfg.intervalo_dias)).isoformat()) if ultimo_digest else "na próxima Coleta"
hoje = date.today()

st.title(cfg.nome)
st.caption("Tudo que saiu sobre a i9+/InoveMais e o setor de baterias, coletado e resumido pelo robô. Nada é descartado; a Relevância só ordena.")

# ---------- Coletar agora (no PC roda aqui; na nuvem liga o robô no GitHub Actions) ----------


def rodar_radar(*args, rotulo="Coleta"):
    """Roda `radar ...` num processo separado e mostra o log ao vivo."""
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    linhas = []
    with st.status(f"{rotulo} em andamento…", expanded=True) as caixa:
        area = st.empty()
        proc = subprocess.Popen([sys.executable, "-m", "radar.cli", *args], cwd=RAIZ, env=env, text=True,
                                encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for linha in proc.stdout:
            linhas.append(linha.rstrip())
            area.code("\n".join(linhas[-25:]), language=None)
        ok = proc.wait() == 0
        caixa.update(label=f"{rotulo} {'concluída' if ok else 'terminou com erro'}", state="complete" if ok else "error", expanded=not ok)
    return ok, "\n".join(linhas)


with st.sidebar:
    if not NUVEM:
        if st.button("Coletar agora", icon=":material/radar:", type="primary", width="stretch",
                     help="Busca notícias novas, resume com a IA e envia os e-mails do dia (se configurados). Leva de 1 a 5 min."):
            ok, log = rodar_radar()
            st.session_state["log_coleta"] = log
            st.rerun()
        if st.session_state.get("log_coleta"):
            with st.expander("Log da última Coleta"):
                st.code(st.session_state["log_coleta"][-4000:], language=None)
    elif GITHUB and liberado():
        if st.button("Coletar agora", icon=":material/radar:", type="primary", width="stretch",
                     help="Liga o robô no GitHub: busca, resume com a IA, envia os e-mails do dia e atualiza este Painel "
                          "(as notícias novas aparecem em 5 a 10 min)."):
            ligar_robo("coleta")
        mostrar_execucoes()
    elif GITHUB:
        with st.expander("Área da equipe", icon=":material/lock:"):
            st.caption("Coletar agora e mudar configurações.")
            campo_senha("senha_lateral")
    else:
        st.caption("O robô coleta sozinho todo dia às 8h.")

st.caption(f"Última Coleta: **{br(ultima)}** · Último Digest: **{br(ultimo_digest)}** · Próximo Digest: **{proximo}** "
           f"(a cada {cfg.intervalo_dias} dias)")

if not mencoes:
    st.info("Ainda não há Menções. Clique em **Coletar agora** na barra lateral (ou rode `uv run radar`) para a primeira busca.")
    st.stop()

# ---------- Dados ----------
df = pd.DataFrame([m.__dict__ for m in mencoes])
df["data"] = df["data"].fillna("").astype(str)
df["sentimento"] = df["sentimento"].fillna("sem análise")
df["tema"] = df["tema"].fillna(SEM)
df["esg"] = df["esg"].fillna("não classificado")
df["destaque"] = df["destaque"].fillna("")
for _col in ("resumo", "fonte", "link", "termo", "idioma", "termos_tecnicos"):  # vazio vira "" (NaN quebraria len/in)
    df[_col] = df[_col].fillna("")
df["vital"] = df["relevancia"].fillna(-1) >= MINIMO
df["conhecida"] = [e_de_fonte_conhecida(cfg, f or "", l or "") for f, l in zip(df["fonte"], df["link"])]

# ---------- Filtros ----------
with st.sidebar:
    st.header("Filtros")
    periodo = st.pills("Período", list(PERIODOS), default="90 dias", key="periodo") or "Tudo"
    so_marca = st.checkbox("Só Menções de marca", key="so_marca", help="Só o que cita a i9+/InoveMais diretamente.")
    so_vital = st.checkbox(f"Só \"leia hoje\" (Relevância {MINIMO}+)", key="so_vital")
    busca = st.text_input("Buscar no título ou resumo", key="busca", placeholder="ex.: Tecpar, lítio, lei…")
    relev = st.slider("Relevância", 0, 10, (0, 10), key="relev")
    temas = st.multiselect("Eixo", [*TEMAS, SEM], key="temas", placeholder="Todos", format_func=lambda t: t.capitalize() if t != "esg" else "ESG")
    esgs = st.multiselect("ESG", [*ESG, "não classificado"], key="esgs", placeholder="Todos")
    sents = st.multiselect("Sentimento", ["positivo", "neutro", "negativo", "sem análise"], key="sents", placeholder="Todos")
    with st.expander("Mais filtros"):
        termos_f = st.multiselect("Termo / fonte", sorted(df["termo"].dropna().unique()), key="termos", placeholder="Todos",
                                  help="Montadoras (BYD…), parceiros, sites (Câmara, Senado, WEF) e buscas.")
        idiomas_f = st.multiselect("Idioma", sorted(df["idioma"].dropna().unique()), key="idiomas", placeholder="Todos")
        so_conhecida = st.checkbox("Só fontes conhecidas", key="so_conhecida", help="Veículos e domínios da lista `fontes_conhecidas` do config.")
    ordem = st.radio("Ordenar por", ["Relevância", "Mais recentes", "Mais antigas"], key="ordem",
                     help="Relevância: Menções da i9+ primeiro, depois a nota da IA.")


def no_periodo(base, inicio, fim):
    """Menção sem data nunca some por causa do período."""
    return base[(base["data"] == "") | ((base["data"] >= inicio.isoformat()) & (base["data"] <= fim.isoformat()))]


dias = PERIODOS[periodo]
f = df
anterior = None
if dias:
    f = no_periodo(df, hoje - timedelta(days=dias), hoje)
    anterior = df[(df["data"] >= (hoje - timedelta(days=2 * dias)).isoformat()) & (df["data"] < (hoje - timedelta(days=dias)).isoformat())]


def aplicar(base):
    if base is None:
        return None
    if so_marca:
        base = base[base["marca"]]
    if so_vital:
        base = base[base["vital"]]
    if relev != (0, 10):
        base = base[base["relevancia"].notna() & base["relevancia"].between(*relev)]
    if temas:
        base = base[base["tema"].isin(temas)]
    if esgs:
        base = base[base["esg"].isin(esgs)]
    if sents:
        base = base[base["sentimento"].isin(sents)]
    if termos_f:
        base = base[base["termo"].isin(termos_f)]
    if idiomas_f:
        base = base[base["idioma"].isin(idiomas_f)]
    if so_conhecida:
        base = base[base["conhecida"]]
    if busca:
        b = busca.lower()
        base = base[base["titulo"].str.lower().str.contains(b, regex=False, na=False)
                    | base["resumo"].fillna("").str.lower().str.contains(b, regex=False)
                    | base["destaque"].str.lower().str.contains(b, regex=False)]
    return base


f, anterior = aplicar(f), aplicar(anterior)


def pct(serie):
    return round(100 * serie.mean()) if len(serie) else None


def favorabilidade(base):
    c = base[base["sentimento"].isin(COR_SENT)] if base is not None else None
    return pct(c["sentimento"] == "positivo") if c is not None and len(c) else None


def delta(atual, ant, sufixo=""):
    return None if ant is None or atual is None else f"{atual - ant:+d}{sufixo}"


def taxa_relevantes(base):
    c = base[base["relevancia"].notna()] if base is not None else None
    return pct(c["relevancia"] >= 7) if c is not None and len(c) else None


def fav_esg(base):
    return favorabilidade(base[base["esg"].isin(COR_ESG)]) if base is not None else None


# ---------- Números grandes (KPIs do mockup Intel Hub) ----------
este_mes = int((df["coletada_em"] >= hoje.replace(day=1).isoformat()).sum())
st.caption(f"Histórico: **{len(df)}** Menções · Coletadas este mês: **{este_mes}**"
           + (f" · Setas: comparação com os {dias} dias anteriores" if dias else ""))
n_ant = len(anterior) if anterior is not None else None
k = st.columns(6)
k[0].metric("Menções", len(f), delta(len(f), n_ant), border=True)
k[1].metric("Da marca", int(f["marca"].sum()),
            delta(int(f["marca"].sum()), int(anterior["marca"].sum()) if anterior is not None else None), border=True,
            help="Citam a i9+/InoveMais no título ou trecho. Disparam Alerta no mesmo dia.")
k[2].metric("Leia hoje", int(f["vital"].sum()), border=True,
            help=f"Relevância {MINIMO} ou mais. Também vão no Alerta do mesmo dia por e-mail.")
tr, tr_ant = taxa_relevantes(f), taxa_relevantes(anterior)
k[3].metric("Relevantes", f"{tr}%" if tr is not None else "—", delta(tr, tr_ant, " p.p."), border=True,
            help="Eficiência do filtro: parcela das Menções analisadas com Relevância 7 ou mais (quanto do que o robô traz vale a leitura).")
fav, fav_ant = favorabilidade(f), favorabilidade(anterior)
k[4].metric("Favorável", f"{fav}%" if fav is not None else "—", delta(fav, fav_ant, " p.p."), border=True,
            help="Favorabilidade: parcela de Menções positivas para a i9+ entre as já classificadas pela IA.")
fe, fe_ant = fav_esg(f), fav_esg(anterior)
k[5].metric("Favorável ESG", f"{fe}%" if fe is not None else "—", delta(fe, fe_ant, " p.p."), border=True,
            help="Favorabilidade à agenda ESG: parcela positiva entre as Menções com eixo ambiental, social ou governança.")


def pill(texto, cor=None):
    return f"<span class='pill' style='background:{cor}'>{texto}</span>" if cor else f"<span class='pill neutra'>{texto}</span>"


def etiquetas(m):
    e = pill(ICONE.get(m["sentimento"], "") + m["sentimento"], COR_SENT.get(m["sentimento"], "#3a3f4a"))
    if m["marca"]:
        e += pill(ICONE["marca"] + "i9+", VERMELHO)
    if m["vital"]:
        e += pill(ICONE["vital"] + "leia hoje", AZUL)
    if m["tema"] and m["tema"] != SEM:
        e += pill("ESG" if m["tema"] == "esg" else m["tema"].capitalize())
    if m["esg"] in COR_ESG:
        e += pill(m["esg"], COR_ESG[m["esg"]])
    if m["conhecida"]:
        e += pill(ICONE["escudo"] + "fonte conhecida")
    return e


def meta(m):
    nota = f"Relevância {int(m['relevancia'])}/10" if pd.notna(m["relevancia"]) else "sem nota"
    fonte = f"<b>{m['fonte']}</b>" if m["fonte"] else ""
    return " · ".join(x for x in [fonte, br(m["data"]) if m["data"] else "", nota] if x)


def cartao(col, m, grande=False):
    resumo = m["resumo"] if m["resumo"] and m["resumo"] != m["titulo"] else ""
    if len(resumo) > 240:
        resumo = resumo[:240].rsplit(" ", 1)[0] + "…"
    with col.container(border=True):
        if grande and m["destaque"]:
            st.markdown(
                f"<div>{etiquetas(m)}</div><div class='destaque'>{m['destaque']}</div>"
                f"<div class='destaque-fonte'>Título original: <a href='{m['link']}' target='_blank'>{m['titulo']}</a></div>"
                f"<div class='meta'>{meta(m)}</div>", unsafe_allow_html=True)
        else:
            dest = f"<div class='resumo' style='font-weight:600;margin-bottom:.2rem'>{m['destaque']}</div>" if m["destaque"] else ""
            st.markdown(
                f"<div>{etiquetas(m)}</div>"
                f"<div class='titulo' style='margin:.4rem 0 .3rem'><a href='{m['link']}' target='_blank'>{m['titulo']}</a></div>"
                f"{dest}<div class='resumo'>{resumo}</div><div class='meta'>{meta(m)}</div>", unsafe_allow_html=True)


# ---------- Leia hoje (o pedido nº 1 da i9+) ----------
vitais = f[f["vital"] | f["marca"]]
recentes = vitais[vitais["coletada_em"] >= (hoje - timedelta(days=2)).isoformat()]
if len(recentes):
    titulo_hoje, sub_hoje, base_hoje = "Leia hoje", f"Relevância {MINIMO}+ ou citação da i9+, coletadas nos últimos 2 dias.", recentes
else:
    titulo_hoje = "Leia primeiro"
    sub_hoje = (f"Nada novo com Relevância {MINIMO}+ nos últimos 2 dias. Estas são as mais recentes do período e filtros escolhidos."
                if len(vitais) else f"Nenhuma Menção com Relevância {MINIMO}+ no período e filtros escolhidos.")
    base_hoje = vitais
st.markdown(f"<div class='hoje'><h3>{titulo_hoje}</h3><p>{sub_hoje}</p></div>", unsafe_allow_html=True)
topo = base_hoje.sort_values(["marca", "data", "relevancia"], ascending=[False, False, False], na_position="last").head(6)
for i in range(0, len(topo), 3):
    for col, (_, m) in zip(st.columns(3), list(topo.iloc[i:i + 3].iterrows())):
        cartao(col, m, grande=True)

# ---------- Abas ----------
if ordem == "Relevância":
    f = f.sort_values(["marca", "relevancia", "data"], ascending=[False, False, False], na_position="last")
else:
    f = f.sort_values(["data", "coletada_em"], ascending=[ordem == "Mais antigas"] * 2, na_position="last")

aba_mencoes, aba_graficos, aba_glossario, aba_avaliacao, aba_como, aba_config = st.tabs(
    ["Menções", "Gráficos", "Glossário", "Avaliação da IA", "Como funciona", "Configurações"])

COLUNAS_CSV = ["data", "titulo", "destaque", "resumo", "fonte", "link", "relevancia", "tema", "esg", "sentimento", "marca",
               "vital", "conhecida", "termo", "idioma", "coletada_em"]

with aba_mencoes:
    t1, t2, t3 = st.columns([2, 1, 1], vertical_alignment="center")
    t1.subheader(f"{len(f)} de {len(df)} Menções")
    t2.download_button("Baixar filtradas (CSV)", f[COLUNAS_CSV].to_csv(index=False).encode("utf-8-sig"), "radar-i9-filtrado.csv",
                       "text/csv", icon=":material/filter_alt:", width="stretch")
    t3.download_button("Baixar tudo (CSV)", df[COLUNAS_CSV].to_csv(index=False).encode("utf-8-sig"), "radar-i9.csv", "text/csv",
                       icon=":material/download:", help="O histórico completo, sem filtro. Abre no Excel.", width="stretch")
    vista = st.segmented_control("Ver como", ["Cartões", "Tabela"], default="Cartões", key="vista", label_visibility="collapsed")
    if vista == "Tabela":
        st.dataframe(f[["data", "titulo", "destaque", "fonte", "sentimento", "tema", "esg", "relevancia", "termo", "link"]],
                     hide_index=True, width="stretch",
                     column_config={"link": st.column_config.LinkColumn("link", display_text="abrir"),
                                    "relevancia": st.column_config.ProgressColumn("relevância", min_value=0, max_value=10, format="%d")})
    else:
        st.session_state.setdefault("limite", 30)
        lote = list(f.head(st.session_state["limite"]).iterrows())
        for i in range(0, len(lote), 3):
            for col, (_, m) in zip(st.columns(3), lote[i:i + 3]):
                cartao(col, m)
        if len(f) > st.session_state["limite"]:
            if st.button(f"Mostrar mais ({len(f) - st.session_state['limite']} restantes)"):
                st.session_state["limite"] += 30
                st.rerun()

PARADAS = set("""a o as os de da do das dos e em no na nos nas um uma para por com sem que se sua seu suas seus mais como ao aos à às
pelo pela pelos pelas é são foi ser ter tem entre sobre até após já não sim the of and to in for on with by from at as is are
be its an or new how what will this that into over after about than more their has have was were can up out energy energia
baterias bateria battery batteries says said data global market markets power project projects report news 2024 2025 2026
2027 2030 2035 sobre deve pode diz após contra ainda anos novo nova novos novas""".split())

with aba_graficos:
    com_data = f[f["data"] != ""].copy()
    if f.empty:
        st.info("Nenhuma Menção no período e filtros escolhidos. Troque o período para \"Tudo\" na barra lateral.")
    elif com_data.empty:
        st.caption("Sem Menções com data no recorte atual.")
    else:
        com_data["dia"] = pd.to_datetime(com_data["data"], errors="coerce")
        com_data = com_data.dropna(subset=["dia"])
        span = (com_data["dia"].max() - com_data["dia"].min()).days
        passo, nome_passo = ("W-MON", "semana") if span > 120 else ("D", "dia")
        serie = com_data.set_index("dia").groupby(pd.Grouper(freq=passo)).agg(Menções=("chave", "count"), **{"Leia hoje": ("vital", "sum")})
        st.markdown(f"**Volume de Menções por {nome_passo}** (data de publicação)")
        longa = serie.reset_index().melt("dia", var_name="Série", value_name="Quantidade")
        st.altair_chart(alt.Chart(longa).mark_line(point=nome_passo == "semana").encode(
            x=alt.X("dia:T", title=None, axis=alt.Axis(format="%d/%m", labelAngle=0)),
            y=alt.Y("Quantidade:Q", title=None),
            color=alt.Color("Série:N", scale=alt.Scale(domain=["Menções", "Leia hoje"], range=[AZUL, VERMELHO]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("dia:T", title="Data", format="%d/%m/%Y"), "Série:N", "Quantidade:Q"],
        ).properties(height=260), width="stretch")

    if len(f):
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Menções por eixo e sentimento**")
            cruz = pd.crosstab(f["tema"], f["sentimento"]).reindex(columns=["positivo", "neutro", "negativo"], fill_value=0)
            cruz = cruz[cruz.sum(axis=1) > 0]
            cruz = cruz.loc[cruz.sum(axis=1).sort_values(ascending=False).index]
            cruz.index = [("ESG" if t == "esg" else t.capitalize()) for t in cruz.index]
            st.bar_chart(cruz, horizontal=True, color=[VERDE, CINZA, VERMELHO], height=260, sort=False)
        with g2:
            st.markdown("**Eixos ESG**")
            esg_cont = f["esg"].value_counts().reindex(["ambiental", "social", "governança", "nenhum", "não classificado"], fill_value=0)
            st.bar_chart(esg_cont.rename("Menções"), horizontal=True, color=VERDE, height=260, sort=False)
        g3, g4 = st.columns(2)
        with g3:
            st.markdown("**Palavras mais frequentes nos títulos**")
            palavras = Counter(p for t in f["titulo"].str.lower() for p in re.findall(r"[a-zà-ú0-9+\-]{4,}", t) if p not in PARADAS)
            st.bar_chart(pd.Series(dict(palavras.most_common(15)), name="vezes"), horizontal=True, color=AZUL, height=380, sort="-vezes")
        with g4:
            st.markdown("**Veículos que mais publicaram**")
            st.bar_chart(f["fonte"].value_counts().head(15).rename("Menções"), horizontal=True, color=AZUL, height=380, sort="-Menções")
    st.caption("Mapa geográfico: as Fontes não informam o país de forma confiável, então ficou de fora desta versão.")

with aba_glossario:
    st.markdown("Siglas e termos técnicos que a IA encontrou nas notícias, explicados em português.")
    itens = {}
    for tt in f["termos_tecnicos"]:
        try:
            for t in json.loads(tt or "[]"):
                chave_t = t["termo"].strip().lower()
                if chave_t not in itens:
                    itens[chave_t] = {"Termo": t["termo"].strip(), "Explicação": t["explicacao"].strip(), "Aparece em": 0}
                itens[chave_t]["Aparece em"] += 1
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    if itens:
        st.dataframe(pd.DataFrame(itens.values()).sort_values(["Aparece em", "Termo"], ascending=[False, True]), hide_index=True, width="stretch")
    else:
        st.info("O glossário é preenchido pela IA a cada notícia nova analisada. Rode uma Coleta com a chave da IA configurada "
                "(ou `uv run radar reclassificar` para refazer o histórico).")

with aba_avaliacao:
    st.markdown("Teste de precisão (Cronograma C19): pessoas dão a própria nota e o eixo a uma amostra de 30 Menções, "
                "sem ver o que a IA disse. O Painel compara e calcula a concordância.")
    avaliador = st.text_input("Seu nome", key="avaliador", placeholder="ex.: Tiago")
    analisadas = df[df["relevancia"].notna() & (df["resumo"] != "")]
    amostra = analisadas.sample(min(30, len(analisadas)), random_state=42) if len(analisadas) else analisadas
    feitas = pd.DataFrame(listar_avaliacoes(DB))
    if avaliador and len(amostra):
        minhas = feitas[feitas["avaliador"] == avaliador.strip()].set_index("chave") if len(feitas) else pd.DataFrame()
        tabela = pd.DataFrame({
            "chave": amostra["chave"].values,
            "Título": amostra["titulo"].values,
            "Resumo": amostra["resumo"].values,
            "Sua nota (0-10)": [minhas["nota_humana"].get(c) if len(minhas) else None for c in amostra["chave"]],
            "Eixo": [minhas["tema_humano"].get(c) if len(minhas) else None for c in amostra["chave"]],
        })
        editada = st.data_editor(tabela, hide_index=True, width="stretch", key="editor_avaliacao", disabled=["Título", "Resumo"],
                                 column_config={"chave": None,
                                                "Sua nota (0-10)": st.column_config.NumberColumn(min_value=0, max_value=10, step=1),
                                                "Eixo": st.column_config.SelectboxColumn(options=list(TEMAS))})
        if st.button("Salvar minhas avaliações", icon=":material/save:"):
            novas = [{"chave": r["chave"], "avaliador": avaliador.strip(), "relevancia": int(r["Sua nota (0-10)"]),
                      "tema": r["Eixo"] if pd.notna(r["Eixo"]) else None, "em": hoje.isoformat()}
                     for _, r in editada.iterrows() if pd.notna(r["Sua nota (0-10)"])]
            salvou = True
            if NUVEM:  # na nuvem a cópia do banco é descartável: a avaliação vai para o avaliacoes.json do repositório
                if not (GITHUB and liberado()):
                    salvou = False
                    st.warning("No Painel publicado, salvar avaliações exige a senha da equipe "
                               "(barra lateral → Área da equipe).")
                else:
                    try:
                        nuvem.salvar_avaliacoes_no_github(REPO, TOKEN, novas, avaliador.strip())
                    except Exception as e:
                        salvou = False
                        st.error(f"Não consegui gravar no GitHub: {e}")
            if salvou:
                for a in novas:
                    gravar_avaliacao(DB, a["chave"], a["avaliador"], a["relevancia"], a["tema"], a["em"])
                st.success(f"{len(novas)} avaliações salvas.")
                st.rerun()
    elif not avaliador:
        st.caption("Digite seu nome para começar.")

    if len(feitas):
        h, ia_ = feitas["nota_humana"], feitas["nota_ia"]
        humano_rel, ia_rel = h >= 7, ia_ >= 7
        vp = int((humano_rel & ia_rel).sum())
        prec = vp / ia_rel.sum() if ia_rel.sum() else 0
        rec = vp / humano_rel.sum() if humano_rel.sum() else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        com_tema = feitas[feitas["tema_humano"].notna()]
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Avaliações", len(feitas), f"{feitas['avaliador'].nunique()} pessoa(s)", delta_color="off", border=True)
        r2.metric("Concordância de nota", f"{pct((h - ia_).abs() <= 2)}%", border=True, help="IA e pessoa com até 2 pontos de diferença.")
        r3.metric("F1 \"vale ler\"", f"{f1:.2f}", border=True,
                  help="Relevância 7+ = vale ler. F1 junta precisão (a IA não exagera) e cobertura (a IA não deixa passar). 1,00 = perfeito.")
        r4.metric("Acerto de eixo", f"{pct(com_tema['tema_humano'] == com_tema['tema_ia'])}%" if len(com_tema) else "—", border=True)
        st.caption(f"Erro médio da nota: {(h - ia_).abs().mean():.1f} ponto(s). Use estes números no Relatório Técnico.")
        st.download_button("Baixar avaliações (CSV)", feitas.to_csv(index=False).encode("utf-8-sig"), "avaliacoes-ia.csv", "text/csv")

with aba_como:
    st.markdown("#### Como o Radar funciona")
    st.graphviz_chart(f"""digraph {{
        rankdir=LR; bgcolor="transparent"; nodesep=.35; ranksep=.5;
        node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, fontcolor="white", color="#3a4150", fillcolor="#1f2530"];
        edge [color="#8a8f99", fontname="Helvetica", fontsize=9, fontcolor="#8a8f99"];
        subgraph cluster_f {{ label="Fontes (RSS público)"; fontcolor="#8a8f99"; color="#3a4150"; fontname="Helvetica";
            g [label="Google News\\npt + en"]; b [label="Bing News\\n(com trecho)"]; r [label="Feeds fixos\\nEmbrapii, Câmara, Senado"]; }}
        c [label="Coleta\\n{len(cfg.termos)} Termos, dedupe", fillcolor="{AZUL}"];
        ia [label="IA (Gemini grátis)\\nresumo, destaque, nota 0-10,\\neixo, ESG, sentimento, glossário", fillcolor="{AZUL}"];
        db [label="Histórico\\nradar.db (SQLite)\\nnada é apagado"];
        al [label="Alerta no mesmo dia\\nmarca + leia hoje", fillcolor="{VERMELHO}"];
        dg [label="Digest\\na cada {cfg.intervalo_dias} dias"];
        p [label="Painel\\nfiltros, gráficos, CSV"];
        g -> c; b -> c; r -> c [label="filtro de palavras"]; c -> db; db -> ia [label="só o que é novo"]; ia -> db;
        db -> al [label="e-mail"]; db -> dg [label="e-mail"]; db -> p;
    }}""", width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Fontes")
        fontes = [{"Fonte": "Google News", "Como": "busca por Termo, pt e en, últimos 2 dias (RSS público)"},
                  {"Fonte": "Bing News", "Como": "mesma busca, traz trecho do corpo (RSS público)"}]
        for fd in cfg.feeds:
            fontes.append({"Fonte": fd["nome"], "Como": "RSS oficial do site" + (" + filtro de palavras" if fd.get("filtro") else "")})
        st.dataframe(pd.DataFrame(fontes), hide_index=True, width="stretch")
        st.markdown(f"**{sum(1 for t in cfg.termos if t.idiomas)} Termos buscados**: " + ", ".join(t.nome for t in cfg.termos if t.idiomas) + ".")
        st.markdown("Sem robô que \"raspa\" páginas (crawler): RSS é o formato que os próprios sites oferecem para "
                    "distribuição, não quebra quando o site muda de layout e não fere termos de uso.")
    with c2:
        st.markdown("#### Exemplo real do que a IA devolve (JSON)")
        exemplos = df[(df["origem"] == "ia") & (df["destaque"] != "")]
        exemplos = exemplos if len(exemplos) else df[df["relevancia"].notna()]
        if len(exemplos):
            ex = exemplos.sort_values(["relevancia", "data"], ascending=False).iloc[0]
            if ex["origem"] != "ia" or not ex["destaque"]:
                st.caption("Exemplo do histórico antigo. Destaque, ESG e glossário vêm preenchidos nas notícias analisadas depois da atualização.")
            st.json({"titulo_original": ex["titulo"], "fonte": ex["fonte"], "resumo": ex["resumo"], "destaque": ex["destaque"],
                     "relevancia": int(ex["relevancia"]), "tema": ex["tema"], "esg": ex["esg"], "sentimento": ex["sentimento"],
                     "termos_tecnicos": json.loads(ex["termos_tecnicos"] or "[]")})
        st.markdown("#### Segurança e LGPD")
        st.markdown("Só notícias públicas; nenhum dado pessoal é coletado. Chaves ficam no arquivo `.env` deste computador "
                    "(nunca no código). Ferramentas gratuitas e de fornecedores conhecidos (Google, Microsoft, Streamlit).")
    regra = int((df["origem"] == "regra").sum())
    if regra:
        st.caption(f"{regra} Menções antigas (antes dos eixos fixos) foram classificadas por regra de palavras. "
                   "Para refazer com a IA: `uv run radar reclassificar`.")

# ---------- Configurações (no PC) ----------


def salvar_config(editar, commit, msg="Salvo. A próxima Coleta já usa.", no_github=None):
    """`editar`: texto do config.toml → texto novo (valida e levanta ValueError). No PC grava o arquivo local;
    na nuvem grava no GitHub (o robô usa na próxima Coleta e o Streamlit republica o Painel em 1–2 min)."""
    no_github = NUVEM if no_github is None else no_github
    try:
        if no_github:
            nuvem.editar_config_no_github(REPO, TOKEN, editar, commit)
        else:
            CONFIG.write_text(editar(CONFIG.read_text(encoding="utf-8")), encoding="utf-8")
    except ValueError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"Não consegui gravar: {e}")
        return
    if no_github:
        st.success(f"{msg} Gravado no GitHub: o Painel mostra a mudança em 1–2 min.")
    else:
        st.toast(msg, icon=":material/check:")
        st.rerun()


def lista_emails(txt):
    emails = [e.strip() for e in re.split(r"[\s,;]+", txt or "") if e.strip()]
    ruins = [e for e in emails if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e)]
    if ruins:
        raise ValueError(f"E-mail inválido: {', '.join(ruins)}")
    return emails


with aba_config:
    if NUVEM and not GITHUB:
        st.info("Painel publicado em modo somente leitura. Para mudar configurações e coletar daqui, configure "
                "GITHUB_TOKEN e SENHA_PAINEL nos Secrets do Streamlit Cloud (ver README).")
    elif not liberado():
        campo_senha("senha_painel", "Senha do Painel")
        st.caption("Digite a senha para mudar as configurações.")
    else:
        brutas = CONFIG.read_text(encoding="utf-8")
        if not NUVEM:
            st.markdown("#### Chaves e e-mail do robô")
            env = ler_dotenv(ENV)
            st.caption(f"IA: **{'configurada' if env.get('GEMINI_API_KEY') or env.get('GROQ_API_KEY') else 'sem chave'}** · "
                       f"E-mail: **{'configurado (' + env['SMTP_USER'] + ')' if env.get('SMTP_USER') and env.get('SMTP_PASS') else 'modo simulado'}**. "
                       "Os valores ficam só neste computador, no arquivo `.env`.")
            with st.form("chaves"):
                a, b = st.columns(2)
                gem = a.text_input("Chave do Gemini", type="password", placeholder="deixe em branco para manter",
                                   help="Grátis em aistudio.google.com/apikey (qualquer conta Google, sem cartão).")
                usr = b.text_input("Gmail que envia (SMTP_USER)", value=env.get("SMTP_USER", ""), placeholder="radar.i9@gmail.com")
                pwd = b.text_input("Senha de app do Gmail", type="password", placeholder="deixe em branco para manter",
                                   help="Conta Google → Segurança → Verificação em 2 etapas → Senhas de app (16 letras).")
                if st.form_submit_button("Salvar chaves", icon=":material/key:"):
                    novos = {"SMTP_USER": usr}
                    if gem:
                        novos["GEMINI_API_KEY"] = gem
                    if pwd:
                        novos["SMTP_PASS"] = pwd
                    try:
                        if not ENV.exists() and (RAIZ / ".env.example").exists():
                            ENV.write_text((RAIZ / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
                        ajustes.gravar_dotenv(ENV, novos)
                        st.toast("Chaves salvas.", icon=":material/check:")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            x, y, _ = st.columns([1, 1, 2])
            if x.button("Testar a IA", icon=":material/psychology:", width="stretch"):
                rodar_radar("fumaca", "ia", rotulo="Teste da IA")
            if y.button("Enviar e-mail de teste", icon=":material/mail:", width="stretch",
                        help="Manda um e-mail para o próprio Gmail configurado."):
                rodar_radar("fumaca", "email", rotulo="Teste de e-mail")
        else:
            st.markdown("#### Chaves e e-mail do robô")
            st.caption("Na nuvem quem usa as chaves é o robô no GitHub, então elas ficam guardadas nos **Secrets do GitHub** "
                       "(`GEMINI_API_KEY`, `SMTP_USER`, `SMTP_PASS`) e nunca aparecem no Painel. Para trocar uma chave, "
                       "abra os Secrets, edite e rode o teste abaixo.")
            x, y, z = st.columns(3)
            x.link_button("Abrir os Secrets do GitHub", f"https://github.com/{REPO}/settings/secrets/actions",
                          icon=":material/key:", width="stretch")
            if y.button("Testar a IA", icon=":material/psychology:", width="stretch"):
                ligar_robo("teste-ia")
            if z.button("Enviar e-mail de teste", icon=":material/mail:", width="stretch",
                        help="O robô manda um e-mail para o próprio Gmail configurado nos Secrets."):
                ligar_robo("teste-email")
            mostrar_execucoes()

        st.markdown("#### Quem recebe e quando")
        with st.form("emails"):
            a, b = st.columns(2)
            alerta_txt = a.text_area("Alerta do mesmo dia (marca + leia hoje)", "\n".join(cfg.email.get("alerta", [])), help="Um e-mail por linha.")
            digest_txt = b.text_area("Digest periódico", "\n".join(cfg.email.get("digest", [])), help="Um e-mail por linha.")
            c, d = st.columns(2)
            intervalo = c.number_input("Digest a cada quantos dias", 1, 60, cfg.intervalo_dias)
            minimo = d.slider("\"Leia hoje\" a partir de Relevância", 5, 10, MINIMO)
            if st.form_submit_button("Salvar", icon=":material/save:"):
                def editar_envio(t):
                    t = ajustes.trocar_valor(t, "email", "alerta", lista_emails(alerta_txt))
                    t = ajustes.trocar_valor(t, "email", "digest", lista_emails(digest_txt))
                    t = ajustes.trocar_valor(t, None, "intervalo_dias", int(intervalo))
                    return ajustes.trocar_valor(t, "alerta", "relevancia_minima", int(minimo))
                salvar_config(editar_envio, "config: destinatários e intervalo (pelo Painel)")

        st.markdown("#### O que é notícia relevante para a i9+")
        with st.form("criterios"):
            crit = st.text_area("A IA dá a nota de 0 a 10 seguindo este texto", cfg.ia.get("criterios", ""), height=200)
            if st.form_submit_button("Salvar critério", icon=":material/save:"):
                salvar_config(lambda t: ajustes.trocar_texto_longo(t, "criterios", crit), "config: critério da IA (pelo Painel)",
                              "Critério salvo. Vale para as próximas análises.")

        st.markdown("#### Termos pesquisados")
        st.dataframe(pd.DataFrame([{"Termo": t.nome, "Busca": t.texto, "Idiomas": ", ".join(t.idiomas) or "só detecta",
                                    "Marca (Alerta)": t.marca} for t in cfg.termos]), hide_index=True, width="stretch", height=240)

        def editar_termos(mensagem, editar):
            salvar_config(editar, mensagem, "Feito. O robô usa a lista nova na próxima Coleta.", no_github=GITHUB)

        with st.form("novo_termo", clear_on_submit=True):
            a, b, c = st.columns([2, 1, 1], vertical_alignment="bottom")
            texto = a.text_input("Novo Termo", placeholder="ex.: Tesla baterias")
            idiomas_n = b.multiselect("Buscar em", ["pt", "en"], default=["pt"], placeholder="Escolha", format_func={"pt": "português", "en": "inglês"}.get)
            marca_n = c.checkbox("É nome da empresa", help="Dispara Alerta no mesmo dia.")
            if st.form_submit_button("Adicionar Termo", icon=":material/add:"):
                editar_termos(f"termos: + {texto} (pelo Painel)", lambda t: adicionar_termo(t, texto, idiomas_n, marca_n))
        a, b = st.columns([3, 1], vertical_alignment="bottom")
        remover = a.selectbox("Remover Termo", ["—", *(t.texto for t in cfg.termos)])
        if b.button("Remover", icon=":material/delete:", disabled=remover == "—", width="stretch"):
            editar_termos(f"termos: - {remover} (pelo Painel)", lambda t: remover_termo(t, remover))
        if not NUVEM:
            st.caption("Feeds RSS e a lista de fontes conhecidas: edite o arquivo `config.toml` (bloco-de-notas) na pasta do Radar.")
        else:
            st.caption(f"Feeds RSS e a lista de fontes conhecidas: edite o [config.toml no GitHub](https://github.com/{REPO}/edit/{RAMO}/config.toml) "
                       "(lápis → *Commit changes*).")

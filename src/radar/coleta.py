"""Uma Coleta inteira: config → fonte → dedupe → IA → histórico → Alerta/Digest."""

import dataclasses
import hashlib
import os
import time
import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from radar import correio, db
from radar.eixos import simples as _simples


@dataclass(frozen=True)
class Noticia:
    titulo: str
    link: str
    fonte: str
    data: str  # ISO (AAAA-MM-DD)
    trecho: str = ""  # pedaço do corpo, quando a Fonte entrega (Bing, Google Alerts, RSS de site)


@dataclass(frozen=True)
class Termo:
    texto: str
    idiomas: tuple[str, ...]
    marca: bool = False
    rotulo: str = ""  # nome que aparece no Painel (ex.: "Fórum Econômico Mundial" para "batteries site:weforum.org")

    @property
    def nome(self) -> str:
        return self.rotulo or self.texto


@dataclass(frozen=True)
class Config:
    nome: str
    intervalo_dias: int
    link_painel: str
    termos: tuple[Termo, ...]
    ia: dict = field(default_factory=dict)
    email: dict = field(default_factory=dict)
    feeds: tuple[dict, ...] = ()  # [[feeds]] nome/url/filtro — RSS/Atom fixos (Google Alerts, sites)
    projeto: str = ""             # prefixo obrigatório do assunto dos e-mails (Manual de Envio de E-mail da i9+)
    alerta: dict = field(default_factory=dict)  # relevancia_minima ("leia hoje"), max_itens
    fontes_conhecidas: tuple[str, ...] = ()     # veículos/domínios confiáveis → selo no Painel

    @property
    def prefixo(self) -> str:
        return self.projeto or self.nome

    @property
    def minimo_vital(self) -> int:
        return int(self.alerta.get("relevancia_minima", 8))


def carregar_config(caminho: Path) -> Config:
    raw = tomllib.loads(Path(caminho).read_text(encoding="utf-8"))
    termos = tuple(
        Termo(t["texto"], tuple(t.get("idiomas", ["pt"])), bool(t.get("marca", False)), t.get("rotulo", ""))
        for t in raw.get("termos", [])
    )
    return Config(
        nome=raw.get("nome", "Radar"),
        intervalo_dias=int(raw.get("intervalo_dias", 7)),
        link_painel=os.environ.get("RADAR_LINK_PAINEL") or raw.get("link_painel", ""),  # nuvem: variável do repositório
        termos=termos,
        ia=raw.get("ia", {}),
        email=raw.get("email", {}),
        feeds=tuple(raw.get("feeds", [])),
        projeto=raw.get("projeto", ""),
        alerta=raw.get("alerta", {}),
        fontes_conhecidas=tuple(raw.get("fontes_conhecidas", [])),
    )


def e_de_marca(cfg: Config, titulo: str, trecho: str = "") -> bool:
    """Só texto da Fonte (título + trecho). O resumo é gerado pela IA e já falou "não há menção à i9+" — nunca conta."""
    alvo = _simples(f"{titulo} {trecho or ''}")
    return any(_simples(t.texto) in alvo for t in cfg.termos if t.marca)


def restringir_busca(cfg: Config, quais: set[str]) -> Config:
    """Coleta de estreia: busca só nos Termos pedidos, mas a detecção de marca continua com TODOS os Termos de marca."""
    termos = []
    for t in cfg.termos:
        if t.texto.lower() in quais or t.nome.lower() in quais:
            termos.append(t)
        elif t.marca:
            termos.append(dataclasses.replace(t, idiomas=()))  # só detecta, não busca
    return dataclasses.replace(cfg, termos=tuple(termos))


def passa_no_filtro(noticia, palavras) -> bool:
    """Feeds genéricos (Câmara, Senado) trazem de tudo: só entra o que cita alguma palavra do filtro."""
    if not palavras:
        return True
    alvo = _simples(f"{noticia.titulo} {noticia.trecho}")
    return any(_simples(p) in alvo for p in palavras)


def e_de_fonte_conhecida(cfg: Config, fonte: str, link: str) -> bool:
    """Selo de veracidade: veículo ou domínio na lista branca do config."""
    from urllib.parse import urlparse
    dominio = urlparse(link or "").netloc.lower().removeprefix("www.")
    nome = _simples(fonte)
    for c in cfg.fontes_conhecidas:
        c_ = _simples(c)
        if ("." in c_ and (dominio == c_ or dominio.endswith("." + c_))) or (c_ and c_ in nome):
            return True
    return False


def chave_de(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()


def _enviar(con, cfg, remetente, tipo, mencoes, montar, hoje_iso, log) -> bool:
    """Envia e registra. Se o e-mail falhar, não registra: a próxima Coleta tenta de novo."""
    assunto, texto, html_ = montar(mencoes)
    try:
        remetente.enviar(list(cfg.email.get(tipo, [])), assunto, texto, html_)
    except Exception as e:
        log(f"{tipo}: falhou o envio ({e}); fica para a proxima Coleta")
        return False
    if getattr(remetente, "simulado", False):
        log(f"{tipo}: simulado, nao registrado — sai de verdade quando houver credenciais")
        return False
    db.registrar_envio(con, tipo, hoje_iso, mencoes)
    con.commit()
    return True


def coletar(cfg: Config, fonte, ia, remetente, hoje: date, db_path: Path, log=print, feeds=None) -> dict:
    con = db.abrir(db_path)
    try:
        return _coletar(cfg, fonte, ia, remetente, hoje, con, log, feeds)
    finally:
        con.close()


def _coletar(cfg, fonte, ia, remetente, hoje, con, log, feeds):
    hoje_iso = hoje.isoformat()
    novas = ignoradas = 0
    for termo in cfg.termos:
        for idioma in termo.idiomas:
            try:
                noticias = fonte.buscar(termo.texto, idioma)
            except Exception as e:  # um feed quebrado não apaga o dia
                log(f"fonte: falhou '{termo.texto}' ({idioma}): {e}")
                continue
            for n in noticias:
                if db.inserir_mencao(con, chave_de(n.link), n, idioma, termo.nome, hoje_iso):
                    novas += 1
                else:
                    ignoradas += 1
    for f in cfg.feeds if feeds else ():  # feeds fixos: o nome do feed faz as vezes do Termo
        try:
            noticias = [n for n in feeds.ler(f["url"], f["nome"]) if passa_no_filtro(n, f.get("filtro", []))]
        except Exception as e:
            log(f"feed: falhou '{f['nome']}': {e}")
            continue
        for n in noticias:
            if db.inserir_mencao(con, chave_de(n.link), n, f.get("idioma", "pt"), f["nome"], hoje_iso):
                novas += 1
            else:
                ignoradas += 1
    db.registrar_coleta(con, hoje_iso, novas, ignoradas)
    con.commit()  # o dia está salvo antes de qualquer chamada de IA
    log(f"coleta: {len(cfg.termos)} termos, {novas} mencoes novas, {ignoradas} ja vistas")

    ok, falhas = analisar_pendentes(cfg, ia, con, log)

    # marca é recalculada para todo o histórico (barato, idempotente; Termos de marca podem mudar no config)
    for m in db.todas(con):
        db.gravar_marca(con, m.chave, e_de_marca(cfg, m.titulo, m.trecho))
    con.commit()

    # Alerta no mesmo dia: Menções de marca + "leia hoje" (Relevância >= mínimo, coletadas nos últimos 2 dias)
    marcas = db.sem_envio(con, "alerta", db.mencoes_de_marca(con))
    desde = (hoje - timedelta(days=2)).isoformat()
    vitais = db.sem_envio(con, "alerta", db.vitais_recentes(con, cfg.minimo_vital, desde))[: int(cfg.alerta.get("max_itens", 10))]
    alerta = marcas + vitais
    enviado = alerta and _enviar(con, cfg, remetente, "alerta", alerta,
                                 lambda ms: correio.montar_alerta(marcas, cfg.link_painel, cfg.nome, vitais=vitais,
                                                                  prefixo=cfg.prefixo, minimo=cfg.minimo_vital), hoje_iso, log)
    oque = f"{len(marcas)} de marca + {len(vitais)} leia hoje"
    log(f"alerta: {'enviado com ' + oque if enviado else ('NAO enviado, ' + oque + ' pendentes' if alerta else 'nada novo')}")

    ultimo = db.ultimo_envio(con, "digest")
    passados = (hoje - date.fromisoformat(ultimo)).days if ultimo else None
    digest = None
    if ultimo is None or passados >= cfg.intervalo_dias:
        pendentes = db.sem_envio(con, "digest", db.todas_ordenadas_para_digest(con))
        enviado = _enviar(con, cfg, remetente, "digest", pendentes,
                          lambda ms: correio.montar_digest(ms, cfg.link_painel, cfg.intervalo_dias, cfg.nome, primeiro=ultimo is None,
                                                          prefixo=cfg.prefixo, minimo=cfg.minimo_vital), hoje_iso, log)
        digest = len(pendentes)
        quando = 'primeiro' if ultimo is None else str(passados) + ' dias desde o ultimo'
        log(f"digest: {'enviado' if enviado else 'NAO enviado'} com {digest} mencoes ({quando})")
    else:
        log(f"digest: nao e dia ({passados} de {cfg.intervalo_dias} dias)")
    return {"novas": novas, "ignoradas": ignoradas, "ia_ok": ok, "ia_falhas": falhas, "alerta": len(marcas), "vitais": len(vitais), "digest": digest}


def analisar_pendentes(cfg: Config, ia, con, log=print, esperar=time.sleep) -> tuple[int, int]:
    """Manda à IA o que está marcado para reprocessar. `[ia] max_por_coleta` e `pausa_segundos` protegem a cota grátis."""
    maximo = int(cfg.ia.get("max_por_coleta", 0) or 0)
    pausa = float(cfg.ia.get("pausa_segundos", 0) or 0)
    pendentes = db.pendentes_de_ia(con)
    if getattr(ia, "sem_chave", False):
        log(f"ia: sem chave configurada, {len(pendentes)} Menções esperando (Painel > Configurações > Chave do Gemini)")
        return 0, 0
    if maximo and len(pendentes) > maximo:
        log(f"ia: {len(pendentes)} pendentes, analisando {maximo} agora (o resto fica para a proxima Coleta)")
        pendentes = pendentes[:maximo]
    ok = falhas = seguidas = 0
    for i, m in enumerate(pendentes):
        if seguidas >= 5:
            log(f"ia: 5 falhas seguidas, parei (sem chave ou cota esgotada?); {len(pendentes) - i} ficam para a proxima Coleta")
            break
        if pausa and i:
            esperar(pausa)
        try:
            a = ia.analisar(m.titulo, m.fonte, m.trecho or "")
            db.gravar_analise(con, m.chave, a["resumo"], a.get("relevancia"), a.get("tema"), a.get("sentimento"),
                              a.get("esg"), a.get("destaque", ""), a.get("termos_tecnicos", []))
            ok += 1
            seguidas = 0
        except Exception as e:  # o robô nunca para por causa do provedor
            db.gravar_falha_de_ia(con, m.chave, m.titulo)
            falhas += 1
            seguidas += 1
            if falhas == 1:
                log(f"ia: falhou '{m.titulo}': {e}")
        if (i + 1) % 25 == 0:
            con.commit()
            log(f"ia: {i + 1}/{len(pendentes)}...")
    con.commit()
    log(f"ia: {ok} ok, {falhas} falhas (ficam para reprocessar)")
    return ok, falhas

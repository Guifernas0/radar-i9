"""E-mails do Radar: montagem do Alerta (marca + "leia hoje") e do Digest, e envio por SMTP do Gmail.

Assunto no padrão do Manual de Envio de E-mail da i9+: "<projeto> - <motivo>" (o `projeto` vem do config.toml).
"""

# ponytail: texto e HTML montados à mão; um template engine só quando o Parceiro pedir layout

import html
import smtplib
from email.message import EmailMessage

TOP_DIGEST = 20  # ponytail: Q13 aberta com o Parceiro; nada some do histórico, só do e-mail
AZUL, VERMELHO = "#1f6fe5", "#d7141c"


def _item_texto(m, minimo=None):
    nota = f" · relevância {m.relevancia}/10" if m.relevancia is not None else ""
    tema = f" · {m.tema}" if m.tema else ""
    vital = " [LEIA HOJE]" if minimo is not None and m.relevancia is not None and m.relevancia >= minimo else ""
    destaque = f"  >> {m.destaque}\n" if getattr(m, "destaque", "") else ""
    return f"• {m.titulo}{vital}\n  {m.fonte} · {m.data}{nota}{tema}\n{destaque}  {m.resumo or ''}\n  {m.link}\n"


def _etiqueta(texto, cor):
    return (f'<span style="background:{cor};color:#fff;border-radius:10px;padding:1px 8px;font-size:11px;'
            f'font-weight:bold;margin-left:6px">{texto}</span>')


def _item_html(m, minimo=None):
    nota = f" · relevância {m.relevancia}/10" if m.relevancia is not None else ""
    tema = f" · {html.escape(m.tema)}" if m.tema else ""
    marca = _etiqueta("MARCA", VERMELHO) if m.marca else ""
    vital = _etiqueta("LEIA HOJE", AZUL) if minimo is not None and m.relevancia is not None and m.relevancia >= minimo else ""
    destaque = (f'<div style="margin:4px 0;font-weight:bold;color:#333">&#9656; {html.escape(m.destaque)}</div>'
                if getattr(m, "destaque", "") else "")
    return (
        f'<div style="margin:0 0 14px;padding:10px 12px;border-left:4px solid {VERMELHO if m.marca else AZUL};background:#f6f8fb">'
        f'<b><a href="{html.escape(m.link)}" style="color:#111;text-decoration:none">{html.escape(m.titulo)}</a></b>{marca}{vital}<br>'
        f'<small style="color:#666">{html.escape(m.fonte or "")} · {m.data}{nota}{tema}</small>{destaque}'
        f'<div style="color:#333">{html.escape(m.resumo or "")}</div></div>'
    )


def _moldura(titulo, corpo, link_painel):
    return (f'<div style="font-family:Arial,sans-serif;max-width:680px">'
            f'<div style="height:5px;background:linear-gradient(90deg,{VERMELHO},{AZUL});border-radius:3px"></div>'
            f'<h2 style="margin:12px 0">{html.escape(titulo)}</h2>{corpo}'
            f'<p><a href="{html.escape(link_painel)}">Abrir o Painel completo</a></p></div>')


def montar_alerta(mencoes, link_painel, nome="Radar i9+", vitais=(), prefixo=None, minimo=8):
    """`mencoes` = Menções de marca; `vitais` = "leia hoje" (Relevância >= mínimo) que não são de marca."""
    prefixo = prefixo or nome
    n, v = len(mencoes), len(vitais)
    partes = []
    if n:
        partes.append(f"Alerta de marca: {n} {'menções' if n != 1 else 'menção'} à i9+/InoveMais hoje")
    if v:
        partes.append(f"{'Alerta ' if not n else ''}leia hoje: {v} {'notícias vitais' if v != 1 else 'notícia vital'}")
    assunto = f"{prefixo} - " + " + ".join(partes)

    texto, corpo = "", ""
    if n:
        texto += f"A i9+/InoveMais foi citada em {n} Menção(ões) encontrada(s) hoje:\n\n" + "\n".join(_item_texto(m) for m in mencoes)
        corpo += f"<h3>A i9+/InoveMais foi citada ({n})</h3>" + "".join(_item_html(m) for m in mencoes)
    if v:
        texto += (f"\nLEIA HOJE — {v} notícia(s) com Relevância {minimo} ou mais:\n\n" + "\n".join(_item_texto(m) for m in vitais))
        corpo += f"<h3>Leia hoje — Relevância {minimo}+ ({v})</h3>" + "".join(_item_html(m) for m in vitais)
    texto += f"\nPainel completo: {link_painel}\n"
    return assunto, texto, _moldura(f"{nome} — Alerta do dia", corpo, link_painel)


def montar_digest(mencoes, link_painel, intervalo_dias, nome="Radar i9+", primeiro=False, prefixo=None, minimo=None):
    prefixo = prefixo or nome
    total = len(mencoes)
    top = mencoes[:TOP_DIGEST]
    restantes = total - len(top)
    n_marca = sum(1 for m in mencoes if m.marca)
    periodo = "desde o início" if primeiro else "desde o último Digest"
    assunto = f"{prefixo} - Digest: {total} menções {periodo}" + (f" ({n_marca} da marca)" if n_marca else "")
    if total == 0:
        texto = f"Nenhuma menção nova {periodo}. O robô continua vigiando (próximo Digest em {intervalo_dias} dias).\nPainel: {link_painel}\n"
        corpo = f"<p>Nenhuma menção nova {periodo}. O robô continua vigiando (próximo Digest em {intervalo_dias} dias).</p>"
        return assunto, texto, _moldura(f"{nome} — Digest", corpo, link_painel)
    rodape = f"\n… e mais {restantes} no Painel: {link_painel}\n" if restantes else f"\nPainel completo: {link_painel}\n"
    texto = (f"{total} menções {periodo} (menções à marca primeiro, depois por relevância):\n\n"
             + "\n".join(_item_texto(m, minimo) for m in top) + rodape)
    corpo = (f"<p>{total} menções {periodo} (marca primeiro, depois por relevância):</p>"
             + "".join(_item_html(m, minimo) for m in top)
             + (f"<p>… e mais <b>{restantes}</b> no Painel.</p>" if restantes else ""))
    return assunto, texto, _moldura(f"{nome} — Digest", corpo, link_painel)


class RemetenteGmail:
    def __init__(self, usuario: str, senha_de_app: str, nome="Radar i9+"):
        self.usuario, self.senha, self.nome = usuario, senha_de_app, nome

    def enviar(self, destinatarios, assunto, texto, html_):
        msg = EmailMessage()
        msg["From"] = f"{self.nome} <{self.usuario}>"
        msg["To"] = ", ".join(destinatarios)
        msg["Subject"] = assunto
        msg.set_content(texto)
        msg.add_alternative(html_, subtype="html")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
            s.login(self.usuario, self.senha)
            s.send_message(msg)


class RemetenteSimulado:
    """Fora do GitHub Actions (ou sem credenciais) só imprime — ninguém recebe e-mail por acidente."""

    simulado = True  # a Coleta não registra o envio: o Digest/Alerta sai de verdade quando houver credenciais

    def __init__(self, log=print):
        self.log = log

    def enviar(self, destinatarios, assunto, texto, html_):
        self.log(f"[simulado] e-mail para {', '.join(destinatarios)}: {assunto}")
        self.log(texto)

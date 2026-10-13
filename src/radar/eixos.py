"""Eixos fixos de classificação pedidos pela i9+ (Roteiro/Cronograma C14 e mockup Intel Hub).

Tema: Tecnologia · Mercado · Legislação · ESG.  ESG: ambiental · social · governança · nenhum.
A IA já responde nesses eixos; este módulo normaliza o que ela devolve e reclassifica o histórico antigo
(anterior aos eixos) por regra de palavras, até alguém rodar `radar reclassificar` com a IA.
"""

import unicodedata

TEMAS = ("tecnologia", "mercado", "legislação", "esg")
ESG = ("ambiental", "social", "governança", "nenhum")
SEM = "sem classificação"


def simples(texto: str) -> str:
    """Sem acento e sem caixa."""
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()


# temas livres que a IA dava antes dos eixos fixos → eixo
_MAPA = {
    "baterias": "tecnologia", "energia solar": "tecnologia", "energia renovavel": "tecnologia", "energia": "tecnologia",
    "inovacao": "tecnologia", "seguranca": "tecnologia", "armazenamento": "tecnologia",
    "concorrencia": "mercado", "parceiros": "mercado", "mobilidade eletrica": "mercado", "minerais criticos": "mercado",
    "economia": "mercado", "investimento": "mercado",
    "regulacao": "legislacao", "politica": "legislacao", "legislacao": "legislacao",
    "economia circular": "esg", "sustentabilidade": "esg", "meio ambiente": "esg", "reciclagem": "esg",
}
_PISTAS_TEMA = (
    ("legislacao", ("regul", "lei", "legisl", "polit", "norma", "govern", "law", "policy")),
    ("esg", ("circular", "ambient", "sustent", "esg", "carbono", "recicl", "social", "clima")),
    ("mercado", ("mercad", "concorr", "preco", "invest", "parceir", "econom", "negoc", "market", "financ")),
)


def normalizar_tema(tema: str | None) -> str:
    s = simples((tema or "").strip())
    if not s or s == simples(SEM):
        return SEM
    for t in TEMAS:
        if s == simples(t):
            return t
    if s in _MAPA:
        return dict(zip(map(simples, TEMAS), TEMAS))[_MAPA[s]]
    for eixo, pistas in _PISTAS_TEMA:
        if any(p in s for p in pistas):
            return dict(zip(map(simples, TEMAS), TEMAS))[eixo]
    return "tecnologia"


def normalizar_esg(valor: str | None) -> str:
    s = simples((valor or "").strip())
    for e in ESG:
        if s == simples(e) or (s and simples(e).startswith(s)):  # aceita "E", "amb", "gov"...
            return e
    return {"e": "ambiental", "s": "social", "g": "governança"}.get(s, "nenhum")


_PISTAS_ESG = {
    "ambiental": ("recicl", "economia circular", "segunda vida", "second-life", "second life", "reuso", "reutiliz",
                  "carbono", "emisso", "descarte", "logistica reversa", "residuo", "sustentab", "meio ambiente",
                  "poluic", "recycling", "circular economy", "emission", "carbon", "waste", "environment", "clima"),
    "governanca": ("lei ", "leis", "projeto de lei", "regulament", "regulac", "norma", "compliance", "governanca",
                   "transparenc", "passaporte", "passport", "regulation", "law", "policy", "diretiva", "anp", "aneel"),
    "social": ("emprego", "trabalhador", "comunidade", "saude", "inclusao", "capacitac", "educac", "jobs",
               "workers", "community", "social"),
}


def esg_por_regra(*textos: str) -> str:
    """Classificação de reserva por palavras (sem IA). Empate: ambiental > governança > social."""
    alvo = f" {simples(' '.join(t or '' for t in textos))} "
    placar = {k: sum(alvo.count(p) for p in ps) for k, ps in _PISTAS_ESG.items()}
    melhor = max(placar, key=placar.get)
    return {"ambiental": "ambiental", "governanca": "governança", "social": "social"}[melhor] if placar[melhor] else "nenhum"

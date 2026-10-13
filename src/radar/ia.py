"""Provedores de IA: um método, texto → JSON. Gemini (plano A) e Groq (plano B), sem SDK."""

import json
import time
import urllib.error
import urllib.request

from radar import eixos

CRITERIOS_PADRAO = """A i9+ / InoveMais (Curitiba-PR) dá segunda vida a baterias de lítio (de carros elétricos, bancos de energia e
equipamentos) e as requalifica para armazenamento de energia, em economia circular. Nota ALTA (8-10): cita a i9+/InoveMais
ou seus parceiros (Lactec, SENAI, Embrapii, Tecpar); lei, norma ou projeto de lei sobre baterias, descarte ou logística
reversa no Brasil; financiamento, edital ou investidor para baterias de segunda vida ou armazenamento; concorrente
brasileiro de reuso/reciclagem de baterias; montadora ou fabricante com programa de segunda vida no Brasil. Nota MÉDIA
(5-7): tecnologia nova de baterias, preço do lítio, mercado global de armazenamento, ESG no setor de energia. Nota BAIXA
(0-4): notícia genérica de energia, carro elétrico sem relação com bateria, propaganda, ou assunto fora do setor."""

PROMPT = """Você analisa notícias para o Radar de uma empresa brasileira de baterias de segunda vida, economia circular
e energia renovável (a i9+ / InoveMais). O que é relevante para ela:
{criterios}

Analise a notícia abaixo e responda SOMENTE um JSON com os campos:
"resumo" (2 a 3 frases em português do Brasil, mesmo que a notícia esteja em outro idioma; descreva SÓ o que a
notícia diz. Os nomes "i9+" e "InoveMais" NUNCA aparecem no resumo — nem para dizer que a notícia não os cita),
"destaque" (UMA frase curta, até 15 palavras, com o dado concreto mais útil da notícia — número, data, lugar ou
empresa —, ex.: "Nova fábrica de baterias de lítio em Camaçari começa a operar em 2027"),
"relevancia" (inteiro de 0 a 10, seguindo os critérios acima),
"tema" (exatamente um de: "tecnologia", "mercado", "legislação", "esg"),
"esg" (exatamente um de: "ambiental", "social", "governança", "nenhum" — o eixo ESG principal da notícia),
"sentimento" ("positivo", "neutro" ou "negativo" para a i9+),
"termos_tecnicos" (lista de no máximo 3 objetos {{"termo": ..., "explicacao": ...}} com siglas ou jargões da notícia
explicados em até 12 palavras em português, ex.: {{"termo": "BESS", "explicacao": "sistema de armazenamento de energia em baterias"}};
lista vazia se não houver).

Título: {titulo}
Fonte: {fonte}
{trecho}"""


def _prompt(titulo, fonte, trecho="", criterios=""):
    return PROMPT.format(titulo=titulo, fonte=fonte, criterios=(criterios or CRITERIOS_PADRAO).strip(),
                         trecho=f"Trecho: {trecho[:1500]}\n" if trecho else "")


def _post_json(url, corpo, cabecalhos, tentativas=4, esperar=time.sleep):
    dados = json.dumps(corpo).encode("utf-8")
    for i in range(tentativas):
        req = urllib.request.Request(url, data=dados, headers={"Content-Type": "application/json", **cabecalhos})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tentativas - 1:
                esperar(2 ** (i + 1))  # 2, 4, 8 s
                continue
            corpo_erro = e.read().decode("utf-8", "replace")[:300].replace("\n", " ")
            raise RuntimeError(f"HTTP {e.code} em {url.split('?')[0]}: {corpo_erro}") from e
        except (urllib.error.URLError, TimeoutError):
            if i < tentativas - 1:
                esperar(2 ** (i + 1))
                continue
            raise


def _json_da_resposta(texto: str) -> dict:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`").removeprefix("json").strip()
    d = json.loads(texto)
    termos = []
    for t in d.get("termos_tecnicos") or []:
        if isinstance(t, dict) and str(t.get("termo", "")).strip() and str(t.get("explicacao", "")).strip():
            termos.append({"termo": str(t["termo"]).strip(), "explicacao": str(t["explicacao"]).strip()})
    return {
        "resumo": str(d.get("resumo", "")).strip(),
        "relevancia": max(0, min(10, int(d.get("relevancia", 0)))),
        "tema": eixos.normalizar_tema(str(d.get("tema", ""))),
        "sentimento": str(d.get("sentimento", "neutro")).strip().lower(),
        "esg": eixos.normalizar_esg(str(d.get("esg", ""))),
        "destaque": str(d.get("destaque", "")).strip(),
        "termos_tecnicos": termos[:3],
    }


class GeminiIA:
    def __init__(self, chave: str, modelo: str = "gemini-3.5-flash-lite", esperar=time.sleep, criterios: str = ""):
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        self.chave, self.esperar, self.criterios = chave, esperar, criterios

    def analisar(self, titulo: str, fonte: str, trecho: str = "") -> dict:
        corpo = {
            "contents": [{"parts": [{"text": _prompt(titulo, fonte, trecho, self.criterios)}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        r = _post_json(self.url, corpo, {"x-goog-api-key": self.chave}, esperar=self.esperar)
        return _json_da_resposta(r["candidates"][0]["content"]["parts"][0]["text"])


class GroqIA:
    """Plano B: API compatível com OpenAI."""

    def __init__(self, chave: str, modelo: str = "openai/gpt-oss-120b", esperar=time.sleep, criterios: str = ""):
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.chave, self.modelo, self.esperar, self.criterios = chave, modelo, esperar, criterios

    def analisar(self, titulo: str, fonte: str, trecho: str = "") -> dict:
        corpo = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": _prompt(titulo, fonte, trecho, self.criterios)}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        r = _post_json(self.url, corpo, {"Authorization": f"Bearer {self.chave}"}, esperar=self.esperar)
        return _json_da_resposta(r["choices"][0]["message"]["content"])


PROVEDORES = {  # provedor → (classe, variável de ambiente da chave, modelo padrão)
    "gemini": (GeminiIA, "GEMINI_API_KEY", "gemini-3.5-flash-lite"),
    "groq": (GroqIA, "GROQ_API_KEY", "openai/gpt-oss-120b"),
}


def variavel_da_chave(cfg_ia: dict) -> str:
    return PROVEDORES[cfg_ia.get("provedor", "gemini")][1]


def criar(cfg_ia: dict, chave: str):
    classe, _, modelo_padrao = PROVEDORES[cfg_ia.get("provedor", "gemini")]
    return classe(chave, cfg_ia.get("modelo") or modelo_padrao, criterios=cfg_ia.get("criterios", ""))

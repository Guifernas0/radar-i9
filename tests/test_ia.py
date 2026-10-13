"""Provedor de IA escolhido por configuração (plano B = Groq), sem rede."""

from radar import ia


def test_provedor_groq_no_config_troca_o_adaptador_e_a_variavel_da_chave():
    cfg_groq = {"provedor": "groq"}
    cfg_gemini = {"provedor": "gemini"}

    assert isinstance(ia.criar(cfg_groq, "chave"), ia.GroqIA)
    assert isinstance(ia.criar(cfg_gemini, "chave"), ia.GeminiIA)
    assert isinstance(ia.criar({}, "chave"), ia.GeminiIA)  # padrão
    assert ia.variavel_da_chave(cfg_groq) == "GROQ_API_KEY"
    assert ia.variavel_da_chave(cfg_gemini) == "GEMINI_API_KEY"


def test_os_dois_provedores_devolvem_o_mesmo_json_a_partir_da_resposta_bruta(monkeypatch):
    bruto = ('```json\n{"resumo": " Texto. ", "relevancia": 12, "tema": "Baterias", "sentimento": "Positivo", "esg": "Ambiental",'
             ' "destaque": " Fábrica em 2027 ", "termos_tecnicos": [{"termo": "BESS", "explicacao": "banco de baterias"}, {"termo": ""}]}\n```')
    monkeypatch.setattr(ia, "_post_json", lambda url, corpo, cab, esperar=None: (
        {"candidates": [{"content": {"parts": [{"text": bruto}]}}]} if "google" in url
        else {"choices": [{"message": {"content": bruto}}]}))

    esperado = {"resumo": "Texto.", "relevancia": 10, "tema": "tecnologia", "sentimento": "positivo", "esg": "ambiental",
                "destaque": "Fábrica em 2027", "termos_tecnicos": [{"termo": "BESS", "explicacao": "banco de baterias"}]}
    assert ia.GeminiIA("k").analisar("t", "f") == esperado
    assert ia.GroqIA("k").analisar("t", "f") == esperado


def test_prompt_usa_criterios_do_config_e_cai_no_padrao_sem_eles():
    assert "REGRA DA EMPRESA" in ia._prompt("t", "f", criterios="REGRA DA EMPRESA")
    assert "segunda vida" in ia._prompt("t", "f")
    assert ia.criar({"criterios": "X"}, "k").criterios == "X"


def test_json_antigo_sem_campos_novos_nao_quebra():
    a = ia._json_da_resposta('{"resumo": "r", "relevancia": 5, "tema": "regulação", "sentimento": "neutro"}')
    assert (a["tema"], a["esg"], a["destaque"], a["termos_tecnicos"]) == ("legislação", "nenhum", "", [])

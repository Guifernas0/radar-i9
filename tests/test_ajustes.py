"""Ajustes locais pelo Painel: .env e config.toml sem estragar o resto do arquivo."""

import tomllib

import pytest

from radar.ajustes import gravar_dotenv, trocar_valor
from radar.cli import ler_dotenv

TOML = '''# comentário do topo
nome = "Radar i9+"
intervalo_dias = 7                      # dias entre Digests

[ia]
provedor = "gemini"

[email]
alerta = ["a@x.com"]   # teste
digest = ["a@x.com"]

[[termos]]
texto = "InoveMais"
idiomas = ["pt"]
'''


def test_trocar_valor_no_topo_e_em_secao_mantem_o_resto():
    novo = trocar_valor(TOML, None, "intervalo_dias", 3)
    novo = trocar_valor(novo, "email", "alerta", ["sandro@i9.com", "b@x.com"])
    novo = trocar_valor(novo, "alerta", "relevancia_minima", 9)  # seção nova
    d = tomllib.loads(novo)
    assert d["intervalo_dias"] == 3 and "# dias entre Digests" in novo and "# comentário do topo" in novo
    assert d["email"] == {"alerta": ["sandro@i9.com", "b@x.com"], "digest": ["a@x.com"]}
    assert d["alerta"]["relevancia_minima"] == 9 and d["termos"][0]["texto"] == "InoveMais"


def test_dotenv_atualiza_sem_perder_comentarios(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# chaves\nGEMINI_API_KEY=            # pegue no AI Studio\nSMTP_USER=\n# RADAR_SIMULAR_ENVIO=1\n", encoding="utf-8")
    gravar_dotenv(p, {"GEMINI_API_KEY": "abc123", "SMTP_PASS": "abcd efgh ijkl mnop"})
    txt = p.read_text(encoding="utf-8")
    assert "# chaves" in txt and "# RADAR_SIMULAR_ENVIO=1" in txt
    assert ler_dotenv(p) == {"GEMINI_API_KEY": "abc123", "SMTP_USER": "", "SMTP_PASS": "abcd efgh ijkl mnop"}
    with pytest.raises(ValueError):
        gravar_dotenv(p, {"X": 'com "aspas"'})


def test_trocar_criterios_de_varias_linhas():
    from radar.ajustes import trocar_texto_longo
    txt = '[ia]\nprovedor = "gemini"\ncriterios = """linha 1\nlinha 2"""\n\n[email]\nalerta = []\n'
    novo = trocar_texto_longo(txt, "criterios", "Nova regra:\nnota alta para leis.")
    d = tomllib.loads(novo)
    assert d["ia"]["criterios"] == "Nova regra:\nnota alta para leis." and d["email"] == {"alerta": []}
    with pytest.raises(ValueError):
        trocar_texto_longo(txt, "criterios", 'com """ aspas')

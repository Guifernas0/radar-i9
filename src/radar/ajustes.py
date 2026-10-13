"""Ajustes pelo Painel quando ele roda no PC (sem GitHub): grava `.env` e troca valores simples do `config.toml`
preservando comentários e o resto do arquivo. Toda escrita é validada antes de ir para o disco."""

import json
import re
import tomllib
from pathlib import Path


def gravar_dotenv(caminho: Path, valores: dict) -> None:
    """Atualiza/insere KEY=valor mantendo as outras linhas (e comentários) do arquivo."""
    linhas = Path(caminho).read_text(encoding="utf-8-sig").splitlines() if Path(caminho).exists() else []
    faltam = dict(valores)
    for i, linha in enumerate(linhas):
        m = re.match(r"\s*#?\s*([A-Z_][A-Z0-9_]*)\s*=", linha)
        if m and m.group(1) in faltam:
            linhas[i] = _linha_env(m.group(1), faltam.pop(m.group(1)))
    linhas += [_linha_env(k, v) for k, v in faltam.items()]
    Path(caminho).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _linha_env(chave, valor):
    valor = (valor or "").strip()
    if "\n" in valor or '"' in valor:
        raise ValueError(f"{chave}: valor inválido.")
    return f'{chave}="{valor}"' if valor else f"{chave}="


def _comentario(linha: str) -> str:
    """O `   # comentário` do fim da linha, ignorando # dentro de strings."""
    dentro = False
    for i, c in enumerate(linha):
        if c == '"' and (i == 0 or linha[i - 1] != "\\"):
            dentro = not dentro
        elif c == "#" and not dentro:
            j = i
            while j > 0 and linha[j - 1] in " \t":
                j -= 1
            return linha[j:]
    return ""


def valor_toml(v) -> str:
    return json.dumps(v, ensure_ascii=False)  # str, int, float, list de str → sintaxe TOML válida


def trocar_valor(toml_txt: str, secao: str | None, chave: str, valor) -> str:
    """Troca `chave = ...` dentro de [secao] (ou no topo, se secao=None); cria a linha se não existir."""
    linhas = toml_txt.splitlines()
    inicio, fim = 0, len(linhas)
    if secao:
        cab = next((i for i, l in enumerate(linhas) if l.strip() == f"[{secao}]"), None)
        if cab is None:
            linhas += ["", f"[{secao}]"]
            cab = len(linhas) - 1
        inicio = cab + 1
    fim = next((i for i in range(inicio, len(linhas)) if linhas[i].lstrip().startswith("[")), len(linhas))
    nova = f"{chave} = {valor_toml(valor)}"
    for i in range(inicio, fim):
        if re.match(rf"\s*{re.escape(chave)}\s*=", linhas[i]):
            linhas[i] = nova + _comentario(linhas[i])
            break
    else:
        pos = fim
        while pos > inicio and not linhas[pos - 1].strip():
            pos -= 1
        linhas.insert(pos, nova)
    novo = "\n".join(linhas) + "\n"
    tomllib.loads(novo)
    return novo


def trocar_texto_longo(toml_txt: str, chave: str, texto: str) -> str:
    """Troca um `chave = \"\"\"...\"\"\"` de várias linhas (ex.: [ia] criterios)."""
    texto = texto.strip().replace("\r\n", "\n")
    if '"""' in texto or "\\" in texto:
        raise ValueError('O texto não pode ter três aspas seguidas nem barra invertida (\\).')
    padrao = re.compile(rf'^{re.escape(chave)}\s*=\s*""".*?"""', re.S | re.M)
    if not padrao.search(toml_txt):
        raise ValueError(f"{chave} não encontrado no config.toml.")
    novo = padrao.sub(lambda _: f'{chave} = """{texto}"""', toml_txt, count=1)
    tomllib.loads(novo)
    return novo

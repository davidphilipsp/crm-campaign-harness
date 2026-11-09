from pathlib import Path

from harness.tools import carrega

INICIO = "<!-- TOOLS:INICIO -->"
FIM = "<!-- TOOLS:FIM -->"


def tabela(caminho_yaml: Path) -> str:
    linhas = ["| tool | zona | resumo |", "|---|---|---|"]
    for t in carrega(caminho_yaml):
        linhas.append(f"| `{t['nome']}` | {t['zona']} | {t['resumo']} |")
    return "\n".join(linhas)


def gera(caminho_yaml: Path, caminho_md: Path) -> None:
    texto = caminho_md.read_text(encoding="utf-8")
    if INICIO not in texto or FIM not in texto:
        raise ValueError(f"{caminho_md}: faltam os marcadores TOOLS")
    antes = texto[: texto.index(INICIO) + len(INICIO)]
    depois = texto[texto.index(FIM) :]
    caminho_md.write_text(f"{antes}\n{tabela(caminho_yaml)}\n{depois}", newline="\n")

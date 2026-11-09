"""Traducao de fact_type_id do Smartico para etapa de funil.

Fonte: references/mensageria.md §6, marcado [doc oficial].
j_communication.fact_type_id:
  1 CREATE · 2 SENT · 3 IMPRESSION · 4 CLICK · 5 FAIL
  6 DELIVERED · 7 OPTOUT · 8 READ · 9 DELETE · 10 SNOOZE
"""

from harness.contracts import EtapaFunilNome

# Ordem do funil, declarada. NAO e a ordem numerica dos codigos:
# SENT(2) -> DELIVERED(6) -> IMPRESSION(3)/READ(8) -> CLICK(4).
ORDEM_FUNIL: tuple[EtapaFunilNome, ...] = ("enviado", "entregue", "aberto", "clicado")

# OPTOUT nao tem etapa de funil (_MAPA[7] = None abaixo) -- contador
# auxiliar de Braco.optout precisa do codigo bruto pra reconhecer a linha,
# ja que etapa_de_fact_type() nao devolve nome nenhum pra ele.
CODIGO_OPTOUT = 7

# IMPRESSION e on-site, READ e e-mail. Ambos sao "aberto", mas NAO sao
# comparaveis entre canais diferentes -- ver planejamento.md §1 e C6.
_MAPA: dict[int, EtapaFunilNome | None] = {
    1: None,  # CREATE   - objeto criado, nao e envio
    2: "enviado",
    3: "aberto",  # IMPRESSION (on-site)
    4: "clicado",
    5: None,  # FAIL     - vira Achado em C3, nao etapa
    6: "entregue",
    7: None,  # OPTOUT
    8: "aberto",  # READ (e-mail)
    9: None,  # DELETE
    10: None,  # SNOOZE
}


def etapa_de_fact_type(codigo: int) -> EtapaFunilNome | None:
    """None = codigo valido que nao e etapa de funil. Desconhecido estoura."""
    if codigo not in _MAPA:
        raise ValueError(f"fact_type_id desconhecido: {codigo}")
    return _MAPA[codigo]

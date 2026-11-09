from collections.abc import Iterator

import pytest

from harness.ingest.pii_guard import PIIEncontrada
from harness.publica.guarda import varre_documento

_CPF_VALIDO = "12345678909"


def _documento(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "versao": 1,
        "gerado_em": "2026-08-01T12:00:00Z",
        "harness_commit": "87076b5",
        "preflights": [
            {
                "fase": "preflight", "casa": "brand_a", "regua": "r", "universo": "csv",
                "base_estimada": 1000, "pct_holdout": "0.05", "conversao_esperada": "0.03",
                "c8": {
                    "veredito": "OK", "n_holdout": 10, "n_tratamento": 90,
                    "mde_absoluto": "0.01", "mde_relativo": "0.1",
                    "piso_amostra": {"valor": "30", "origem": "default_nao_validado"},
                    "piso_mde_ok": {"valor": "0.25", "origem": "crm_md"},
                    "alternativas": [],
                },
                "c9": {"check": "C9", "aprova": True, "motivo": ""},
                "c11": {"check": "C11", "aprova": False, "motivo": "atraso no flow"},
            }
        ],
        "leituras": [
            {
                "fase": "leitura", "casa": "brand_a", "universo": "csv",
                "campanha_id": "9000001",
                "janela_inicio": "2026-07-01T00:00:00Z", "janela_fim": "2026-07-08T00:00:00Z",
                "hipotese": "oferta converte mais que a generica", "contexto": "",
                "digest_hash": "a" * 64,
                "bracos": [
                    {"nome": "tratamento", "etapas": [
                        {"nome": "enviado", "valor": "1000", "rotulo": "medido"},
                    ]},
                ],
                "c3": {
                    "veredito": "verde",
                    "piso_usado": {"valor": "0.85", "origem": "default_nao_validado"},
                    "achados": [
                        {"gate": "C3", "braco": "tratamento",
                         "resumo": "entrega=0.66 abaixo do piso 0.85",
                         "evidencia": {"enviado": "1000", "entregue": "660"}}
                    ],
                },
                "c2": None,
                "achados": [
                    {"tipo": "ctor_anomalo", "resumo": "ctor alto",
                     "evidencia": {"<=0s": "12"}},
                ],
            }
        ],
    }
    base.update(overrides)
    return base


def test_documento_sem_pii_passa() -> None:
    varre_documento(_documento())


def test_documento_com_cpf_no_campanha_id_e_recusado() -> None:
    """Antes desta varredura virar allowlist, campanha_id ficava de fora por
    nao estar em _CAMPOS_DE_RISCO (denylist) -- exatamente o furo que a
    inversao fecha: campanha_id e string escrita pelo operador via --campanha,
    nao coluna tecnica em massa (o argumento estatistico de
    harness/ingest/pii_guard.py COLUNAS_ID_TECNICO nao se aplica a um unico
    escalar). Sem prova em fixture real de que precisa de allowlist, fica
    varrido por padrao."""
    doc = _documento()
    doc["leituras"][0]["campanha_id"] = _CPF_VALIDO  # type: ignore[index]
    with pytest.raises(PIIEncontrada):
        varre_documento(doc)


def test_documento_com_cpf_no_contexto_e_recusado() -> None:
    doc = _documento()
    doc["leituras"][0]["contexto"] = f"conversa com o {_CPF_VALIDO}"  # type: ignore[index]
    with pytest.raises(PIIEncontrada):
        varre_documento(doc)


def test_documento_com_cpf_na_hipotese_e_recusado() -> None:
    doc = _documento()
    doc["leituras"][0]["hipotese"] = f"o {_CPF_VALIDO} sempre converte"  # type: ignore[index]
    with pytest.raises(PIIEncontrada):
        varre_documento(doc)


def test_documento_com_cpf_no_resumo_de_achado_e_recusado() -> None:
    doc = _documento()
    doc["leituras"][0]["c3"]["achados"][0]["resumo"] = _CPF_VALIDO  # type: ignore[index]
    with pytest.raises(PIIEncontrada):
        varre_documento(doc)


def test_documento_com_cpf_no_motivo_de_c11_e_recusado() -> None:
    doc = _documento()
    doc["preflights"][0]["c11"]["motivo"] = _CPF_VALIDO  # type: ignore[index]
    with pytest.raises(PIIEncontrada):
        varre_documento(doc)


def test_documento_com_cpf_em_alternativas_e_recusado() -> None:
    doc = _documento()
    doc["preflights"][0]["c8"]["alternativas"] = [_CPF_VALIDO]  # type: ignore[index]
    with pytest.raises(PIIEncontrada):
        varre_documento(doc)


def test_documento_com_email_no_contexto_e_recusado() -> None:
    doc = _documento()
    doc["leituras"][0]["contexto"] = "falar com joao@example.com"  # type: ignore[index]
    with pytest.raises(PIIEncontrada):
        varre_documento(doc)


def test_mensagem_de_erro_nunca_carrega_o_valor() -> None:
    doc = _documento()
    doc["leituras"][0]["contexto"] = f"conta {_CPF_VALIDO}"  # type: ignore[index]
    with pytest.raises(PIIEncontrada) as exc:
        varre_documento(doc)
    assert _CPF_VALIDO not in str(exc.value)


def _copia_com_valor(no: object, caminho: tuple[str | int, ...], valor: str) -> object:
    """Copia rasa ao longo de `caminho`, com o valor final trocado por `valor`."""
    if not caminho:
        return valor
    chave, resto = caminho[0], caminho[1:]
    if isinstance(no, dict) and isinstance(chave, str):
        novo: dict[str, object] = dict(no)
        novo[chave] = _copia_com_valor(no[chave], resto, valor)
        return novo
    if isinstance(no, list) and isinstance(chave, int):
        nova: list[object] = list(no)
        nova[chave] = _copia_com_valor(no[chave], resto, valor)
        return nova
    raise TypeError(f"caminho {caminho!r} nao navega em {no!r}")


def _todos_os_caminhos_de_string(
    no: object, caminho: tuple[str | int, ...] = ()
) -> Iterator[tuple[str | int, ...]]:
    """Descobre TODO caminho de string do documento -- sem lista de campos
    escrita a mao. Espelha a forma de _valores_de_risco, mas sem allowlist:
    usada para provar que o scanner real cobre cada caminho encontrado."""
    if isinstance(no, dict):
        for chave, valor in no.items():
            yield from _todos_os_caminhos_de_string(valor, (*caminho, chave))
    elif isinstance(no, list):
        for i, item in enumerate(no):
            yield from _todos_os_caminhos_de_string(item, (*caminho, i))
    elif isinstance(no, str):
        yield caminho


def test_todo_caminho_de_string_do_documento_e_varrido() -> None:
    """Anti-recaida da inversao denylist->allowlist. O documento de exemplo
    ja cobre os tres pontos que a varredura antiga deixava passar -- nome de
    braco (leituras[0].bracos[0].nome), evidencia (achados[*].evidencia.*) --
    e ganha aqui um quarto campo, aninhado a tres niveis, que a producao
    ainda nao gera hoje. Sem lista de campos escrita a mao: descobre todo
    caminho de string, planta CPF em cada um, exige recusa em todos."""
    base = _documento()
    base["leituras"][0]["campo_futuro_ainda_nao_existe"] = {  # type: ignore[index]
        "nivel2": {"nivel3": "texto sem pii, so para existir o caminho"}
    }
    caminhos = list(_todos_os_caminhos_de_string(base))
    assert len(caminhos) > 10  # sanidade: documento rico o bastante pra valer o teste

    for caminho in caminhos:
        doc = _copia_com_valor(base, caminho, _CPF_VALIDO)
        assert isinstance(doc, dict)
        with pytest.raises(PIIEncontrada, match=r"cpf"):
            varre_documento(doc)

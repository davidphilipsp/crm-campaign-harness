from harness.squads import squads_validos


def test_registry_tem_os_dois_squads_conhecidos() -> None:
    assert squads_validos() == frozenset({"brand-a-risk-squad", "brand-b-financial-squad"})

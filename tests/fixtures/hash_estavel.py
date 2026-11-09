from decimal import Decimal

from harness.contracts import Braco, Digest, EtapaFunil, Numero
from harness.digest import digest_hash

e = EtapaFunil("enviado", Numero(Decimal("1000"), "medido"))
b = Braco("tratamento", (e,))
d = Digest(
    casa="brand_a",
    fase="leitura",
    universo="csv",
    campanha_id="C-42",
    janela_inicio="2026-07-01T00:00:00Z",
    janela_fim="2026-07-08T00:00:00Z",
    hipotese="oferta converte mais que generica",
    contexto="",
    bracos=(b,),
    proveniencia={"fonte": "teste"},
)
print(digest_hash(d.como_dict()))

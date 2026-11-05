"""Welke bron en welk catalogus-ID achter een ID of datasleutel zit: de enige plek in de chat (#912, #914).

Het ID-contract `bron:id` staat in het pakket (`onderwijsbronnen.parse_bron_id`, `_kern/bron_id.py`): één
normalisatie voor alle acht bronnen, en een kale ID die bij twee bronnen past is een fout met opties. De chat volgt
alleen dat contract; de oude herleiding en de vlag `BRON_ID_CONTRACT` zijn na de acceptatie weggehaald (#913, #914).

Drie vragen, drie functies:

- `bron_id`: het catalogus-ID zonder voorvoegsel (`duo:p01hoinges`, `P01HOINGES` → `p01hoinges`);
- `cbs_tabel_id`: hetzelfde aan de toolgrens van CBS (#370), waar een ID van een andere bron blijft zoals het is;
- `bron_van`: de bron van een datasleutel uit de store (`duo:p01hoinges:4` → `duo`, `analysis:…` → `analysis`).

Een onbekend ID blijft zoals het was (zonder voorvoegsel), zodat de tool daarna zelf "onbekend" meldt. Oude ID-vormen
in opgeslagen recepten blijven werken: het contract accepteert ze allemaal als alias (tests/test_bron_id_vormen.py).
"""

from __future__ import annotations

from onderwijsbronnen import OnbekendBronId, bron_van_sleutel, parse_bron_id

from .canoniek import zonder_bronprefix, zonder_cbs_prefix


def bron_id(dataset_id: str) -> str:
    """Het catalogus-ID achter een genamespaced of anders gespeld ID (#356, #912).

    `duo:p01hoinges`, `rio/erkenningen`, `cbs_85423ned` en `P01HOINGES` wijzen naar het ID zoals de catalogus het
    schrijft, zonder voorvoegsel. Een onbekend ID blijft zoals het is, zonder voorvoegsel.
    """
    try:
        return parse_bron_id(dataset_id).id
    except OnbekendBronId:
        return zonder_bronprefix(dataset_id)


def cbs_tabel_id(dataset_id: str) -> str:
    """Het ID van een CBS-tabel in de spelling van de catalogus (#370, #912): `cbs:85423NED`, `85423ned` → `85423NED`,
    en `71733NED` → `71733ned`, nooit `upper()`. Een ander of onbekend ID blijft zoals het is, zonder `cbs:`."""
    try:
        gevonden = parse_bron_id(dataset_id)
    except OnbekendBronId:
        return zonder_cbs_prefix(dataset_id)
    return gevonden.id if gevonden.bron == "cbs" else zonder_cbs_prefix(dataset_id)


def bron_van(key: str) -> str:
    """De bron van een store-key (duo, cbs, rio, …): uit de meta, anders het voorvoegsel van de key."""
    from . import store  # hier: store importeert tools.catalog, en die deze module

    if known := store.meta(key):
        return known.bron
    return bron_van_sleutel(key)

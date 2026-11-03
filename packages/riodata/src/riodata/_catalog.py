"""Samenvoegen van bronmetadata en verrijking tot één catalogusrecord.

Een catalogusrecord bestaat uit drie lagen met elk een eigen herkomst:

- **bron**: velden uit het basisbestand (``duo_resources.json``, ``rio_resources_ai.json``).
  Deze worden altijd uit het basisbestand genomen, dus bronupdates en nieuwe
  contractvelden komen er direct doorheen.
- **afgeleid**: schema-informatie uit de echte data (``_kolommen``, ``_kolomtypes``, ...).
- **annotatie**: gecontroleerde teksten (``samenvatting``, ``niet_geschikt_voor``, ...).

Afgeleide velden en annotaties komen uit het ``*_enriched.json``-bestand. Een inputhash
(``_verrijking.input_sha256``) laat zien of die verrijking nog bij de bron past.
"""
from __future__ import annotations

import hashlib
import json

SCHEMA_VERSIE = 1

AFGELEID = ("_kolommen", "_kolomtypes", "_kolomdefinities", "kolomtoelichting", "waardenbereik")
ANNOTATIE = ("samenvatting", "niet_geschikt_voor")
# RIO-annotaties die in het enriched-bestand zijn bijgewerkt en daar leidend zijn.
ANNOTATIE_RIO = ("tags", "voorbeeldvragen", "combineerbaar_met")

VERRIJKT_DUO = frozenset(AFGELEID + ANNOTATIE)
VERRIJKT_RIO = frozenset(AFGELEID + ANNOTATIE + ANNOTATIE_RIO)

STAMP = "_verrijking"
STATUS = "_verrijking_status"


def record_id(record: dict) -> str | None:
    return record.get("_ckan_id") or record.get("_rio_resource")


def input_hash(record: dict, verrijkt: frozenset[str]) -> str:
    """Hash van de bronvelden van een record (alles behalve verrijking en eigen markers)."""
    bron = {k: v for k, v in record.items() if k not in verrijkt and k not in (STAMP, STATUS)}
    payload = json.dumps(bron, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stamp(record: dict, verrijkt: frozenset[str]) -> dict:
    return {"input_sha256": input_hash(record, verrijkt), "schema_versie": SCHEMA_VERSIE}


def verrijking_status(base: dict, enriched: dict | None, verrijkt: frozenset[str]) -> str:
    """``actueel``, ``verouderd``, ``ongecontroleerd`` (geen stempel) of ``geen``."""
    if enriched is None:
        return "geen"
    s = enriched.get(STAMP)
    if not s:
        return "ongecontroleerd"
    if s.get("schema_versie") != SCHEMA_VERSIE or s.get("input_sha256") != input_hash(base, verrijkt):
        return "verouderd"
    return "actueel"


def merge(base: list[dict], enriched: list[dict], verrijkt: frozenset[str]) -> list[dict]:
    """Voeg verrijking toe aan het basisbestand.

    - Volgorde en bestaan van records volgen het basisbestand.
    - Bronvelden komen altijd uit de basis; nieuwe basisvelden verschijnen direct.
    - Afgeleide velden en annotaties komen uit de verrijking, behalve als die verouderd is
      (stempel past niet bij de bron): dan blijft de verrijking weg, worden ook de afgeleide
      velden uit het basisbestand (die bij een oude bron horen) verwijderd en staat de status
      op ``verouderd``. Annotaties uit de basis blijven staan; die zijn geen schema.
    - Een verrijking zonder stempel (oudere bestanden) blijft gelden, als ``ongecontroleerd``.
    """
    per_id = {record_id(e): e for e in enriched if record_id(e)}
    out = []
    for b in base:
        e = per_id.get(record_id(b))
        status = verrijking_status(b, e, verrijkt)
        record = {k: v for k, v in b.items() if k not in (STAMP, STATUS)}
        if e is not None and status == "verouderd":
            for k in AFGELEID:
                record.pop(k, None)
        elif e is not None:
            record.update({k: e[k] for k in verrijkt if k in e})
        if e is not None:
            record[STATUS] = status
        out.append(record)
    return out

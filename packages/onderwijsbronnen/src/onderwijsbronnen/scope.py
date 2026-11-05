"""Productscope mbo/hbo/wo: expliciete scopestatus per catalogusrecord.

De toepassing werkt alleen voor mbo, hbo en wo. Een record krijgt de status
``buiten_scope`` als daar een besluit en onderbouwing voor is. Alles zonder besluit is
``onbekend``: geen automatische toelating en geen automatische uitsluiting. Een positieve
status (``in_scope``) bestaat bewust nog niet; die vraagt geverifieerde sectordekking per
resource.
"""
from __future__ import annotations

BUITEN_SCOPE = "buiten_scope"
ONBEKEND = "onbekend"


def scope_status(record: dict) -> str:
    """``buiten_scope`` als het record dat expliciet zegt, anders ``onbekend``."""
    return (record.get("_scope") or {}).get("mbo_hbo_wo", ONBEKEND)


def buiten_scope(record: dict) -> bool:
    return scope_status(record) == BUITEN_SCOPE

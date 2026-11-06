"""Wat elke bron levert, hoe ze ook heet (#911).

Elk bron-subpakket (`cbs`, `duo`, `rio`, `roa`, `uwv`, `inspectie`, `sbb`, `unl`, `skdb`) heeft dezelfde publieke interface:

- `BRON`: de korte naam van de bron, zoals in `onderwijsbronnen.BRONNEN`;
- `catalogusrecords()`: de catalogusrecords van de bron, offline, zonder argumenten aan te roepen;
- `laad`: de functie die de data van de bron ophaalt (`cbs.data`, `rio.fetch`, anders `load`);
- `metadata(record)`: per catalogusrecord dezelfde metadatavelden, gemaakt met `metadata()` hieronder.

Een veld dat een bron niet kan leveren, is `None` met een reden in `redenen`, nooit stil leeg: zo weet de lezer of
de waarde ontbreekt in de bron of dat de bron haar per bestand of per rij levert. `controleer()` is de toets die de
contracttest per bron gebruikt.
"""

from __future__ import annotations

VELDEN = ("bron", "id", "titel", "peildatum_of_editie", "voorlopig", "laatste_update")
INTERFACE = ("BRON", "catalogusrecords", "laad", "metadata")


def metadata(
    bron: str,
    id: str,
    titel: str | None,
    *,
    peildatum_of_editie: str | None = None,
    voorlopig: bool | None = None,
    laatste_update: str | None = None,
    redenen: dict[str, str] | None = None,
) -> dict:
    """De metadata van één catalogusrecord; een reden telt alleen voor een veld dat `None` is."""
    waarden = {
        "bron": bron,
        "id": id,
        "titel": titel,
        "peildatum_of_editie": peildatum_of_editie,
        "voorlopig": voorlopig,
        "laatste_update": laatste_update,
    }
    redenen = redenen or {}
    return {**waarden, "redenen": {veld: redenen[veld] for veld in VELDEN if waarden[veld] is None and veld in redenen}}


def controleer(meta: dict, bron: str) -> list[str]:
    """Wat er mis is aan de metadata van een record van `bron`; leeg als hij aan het contract voldoet."""
    fouten = [f"veld {veld} ontbreekt" for veld in (*VELDEN, "redenen") if veld not in meta]
    if fouten:
        return fouten
    if meta["bron"] != bron:
        fouten.append(f"bron is {meta['bron']!r}, verwacht {bron!r}")
    for veld in ("id", "titel"):
        if not isinstance(meta[veld], str) or not meta[veld]:
            fouten.append(f"{veld} is verplicht en leeg")
    for veld in VELDEN:
        waarde = meta[veld]
        if waarde is None and not meta["redenen"].get(veld):
            fouten.append(f"{veld} is None zonder reden")
        if waarde is not None and veld in meta["redenen"]:
            fouten.append(f"{veld} heeft een waarde én een reden")
        if isinstance(waarde, str | list | dict) and not waarde:
            fouten.append(f"{veld} is stil leeg ({waarde!r}); gebruik None met een reden")
    if meta["voorlopig"] is not None and not isinstance(meta["voorlopig"], bool):
        fouten.append("voorlopig is geen bool")
    return fouten

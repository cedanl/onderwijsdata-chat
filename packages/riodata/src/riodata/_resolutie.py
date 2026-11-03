"""Eén resource kiezen uit de bestanden van een dataset, voor alle loaders.

Volgorde: stabiele ID (UUID/file-ID) → index → exacte naam → unieke naam-substring.
Een substring die meerdere bestanden raakt is een fout met de opties erbij; er wordt
nooit stil de eerste gekozen. Negatieve of te grote indices worden expliciet geweigerd.
"""
from __future__ import annotations


class ResourceFout(LookupError):
    """Basis voor fouten bij het kiezen van een resource."""


class ResourceNietGevonden(ResourceFout, ValueError):
    """Geen resource met deze ID of naam (ValueError voor achterwaartse compatibiliteit)."""

    def __init__(self, bericht: str, opties: list[dict]):
        super().__init__(bericht)
        self.opties = opties


class AmbigueResource(ResourceFout, ValueError):
    """De naam-substring past op meer dan één resource; ``opties`` noemt ze allemaal."""

    def __init__(self, bericht: str, opties: list[dict]):
        super().__init__(bericht)
        self.opties = opties


class ResourceIndexFout(ResourceFout, IndexError):
    """Index buiten bereik of negatief (IndexError voor achterwaartse compatibiliteit)."""


def _optie(item: dict, i: int, id_key: str | None) -> dict:
    optie = {"index": i, "naam": item.get("naam")}
    if id_key and item.get(id_key) not in (None, ""):
        optie["id"] = item[id_key]
    return optie


def kies(items: list[dict], resource: int | str, dataset_id: str, *, id_key: str | None = "id") -> dict:
    """Kies één item uit ``items`` (dicts met minstens ``naam``)."""
    opties = [_optie(it, i, id_key) for i, it in enumerate(items)]
    if isinstance(resource, bool) or not isinstance(resource, (int, str)):
        raise TypeError(f"resource moet een index (int) of ID/naam (str) zijn, niet {type(resource).__name__}")
    if isinstance(resource, int):
        if resource < 0 or resource >= len(items):
            raise ResourceIndexFout(
                f"Dataset '{dataset_id}' heeft {len(items)} resources (index 0 t/m {len(items) - 1}); "
                f"index {resource} bestaat niet."
            )
        return items[resource]
    sleutel = resource.strip()
    if id_key:
        for it in items:
            if str(it.get(id_key, "")).lower() == sleutel.lower() and sleutel:
                return it
    exact = [it for it in items if (it.get("naam") or "").lower() == sleutel.lower()]
    if len(exact) == 1:
        return exact[0]
    matches = [(i, it) for i, it in enumerate(items) if sleutel.lower() in (it.get("naam") or "").lower()]
    if len(matches) == 1:
        return matches[0][1]
    if not matches:
        raise ResourceNietGevonden(
            f"Geen resource '{resource}' in dataset '{dataset_id}'. "
            f"Beschikbaar: {[o['naam'] for o in opties]}",
            opties,
        )
    gevonden = [_optie(it, i, id_key) for i, it in matches]
    raise AmbigueResource(
        f"'{resource}' past op {len(matches)} resources in dataset '{dataset_id}'; "
        f"kies er één via ID of exacte naam: {[o['naam'] for o in gevonden]}",
        gevonden,
    )

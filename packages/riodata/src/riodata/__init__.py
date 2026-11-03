from importlib.metadata import PackageNotFoundError, version as _version

try:  # één versiebron: pyproject.toml, via de geïnstalleerde distributie
    __version__ = _version("riodata")
except PackageNotFoundError:  # broncode zonder installatie
    __version__ = "0+onbekend"

from .client import fetch, get, related
from . import duo, roa, uwv, inspectie, sbb, crebo
from . import _catalog
from . import contract
from ._resolutie import AmbigueResource, ResourceNietGevonden
from ._filtercontract import filtercontract, typewaarden, valideer_filters


def catalog(source: str = "rio", ai: bool = True, live: bool = False) -> list[dict]:
    """Geef catalogusrecords terug.

    Args:
        source: "rio"       — alleen RIO LOD API resources (lokale JSON, snel)
                "duo"       — alleen DUO datasets (lokale snapshot)
                "roa"       — alleen ROA arbeidsmarktdata
                "uwv"       — alleen UWV Open Match Data
                "inspectie" — alleen Inspectie van het Onderwijs datasets
                "sbb"       — alleen SBB kwalificatiestructuur datasets
                "all"       — alles gecombineerd
        ai:     Bij source="rio"/"all": gebruik AI-verrijkte beschrijvingen (default True).
        live:   Bij source="duo"/"all": haal DUO-records live op van CKAN i.p.v. lokale
                snapshot (default False). Vereist internetverbinding.
    """
    import json
    from importlib.resources import files

    data_dir = files("riodata.data")

    def _read(filename):
        return json.loads(data_dir.joinpath(filename).read_text(encoding="utf-8"))

    def _met_verrijking(base_file, enriched_file, verrijkt):
        # Bronvelden komen altijd uit het basisbestand; verrijking wordt eroverheen gelegd.
        base = _read(base_file)
        try:
            enriched = _read(enriched_file)
        except FileNotFoundError:
            return base
        return _catalog.merge(base, enriched, verrijkt)

    def _rio():
        if ai:
            return _met_verrijking("rio_resources_ai.json", "rio_resources_enriched.json", _catalog.VERRIJKT_RIO)
        return _read("rio_resources.json")

    def _duo():
        if live:
            return duo.catalog()
        records = _met_verrijking("duo_resources.json", "duo_resources_enriched.json", _catalog.VERRIJKT_DUO)
        from .duo_notes import zoekkaart_tijd
        for r in records:
            if r.get("_tijd"):
                r["_zoekkaart"] = {**(r.get("_zoekkaart") or {}), "tijd": zoekkaart_tijd(r["_tijd"])}
        return records

    def _roa():
        return json.loads(files("riodata.data").joinpath("roa_resources.json").read_text(encoding="utf-8"))

    def _uwv():
        return json.loads(files("riodata.data").joinpath("uwv_resources.json").read_text(encoding="utf-8"))

    def _inspectie():
        return json.loads(files("riodata.data").joinpath("inspectie_resources.json").read_text(encoding="utf-8"))

    def _sbb():
        return json.loads(files("riodata.data").joinpath("sbb_resources.json").read_text(encoding="utf-8"))

    if source == "rio":
        return _rio()
    if source == "duo":
        return _duo()
    if source == "roa":
        return _roa()
    if source == "uwv":
        return _uwv()
    if source == "inspectie":
        return _inspectie()
    if source == "sbb":
        return _sbb()
    if source == "all":
        return _rio() + _duo() + _roa() + _uwv() + _inspectie() + _sbb()
    raise ValueError(
        f"Ongeldige source '{source}'. "
        f"Kies 'rio', 'duo', 'roa', 'uwv', 'inspectie', 'sbb' of 'all'."
    )


__all__ = ["fetch", "get", "related", "catalog", "filtercontract", "typewaarden", "valideer_filters", "duo", "roa", "uwv", "inspectie", "sbb", "crebo", "contract", "AmbigueResource", "ResourceNietGevonden", "__version__"]

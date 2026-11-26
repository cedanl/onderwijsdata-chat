"""Het opgenomen antwoord van CBS 85081NED (`tests/fixtures/cbs/85081NED_beroepen.json`) als nagebootste OData-bron.

Zoals tests/cbs_83599ned.py: `zet_klaar` vervangt `httpx` in de CBS-client van onderwijsbronnen, zodat de lader
(data/vacatures_ontstaan.py) door de echte client gaat (DataProperties, dimensie, Perioden en de `$filter` op alle
economische activiteiten), maar zonder netwerk. Een aanroep naar een andere tabel gaat door naar de `httpx` die er al
stond: zo werken beide opnames samen. `aanpassen` wijzigt een kopie van het antwoord voordat de bron het geeft.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import httpx

PAD = Path(__file__).parent / "fixtures" / "cbs" / "85081NED_beroepen.json"
FILTER = "BedrijfstakkenBranchesSBI2008 eq 'T001081'"


def opname() -> dict:
    return json.loads(PAD.read_text(encoding="utf-8"))


def _antwoord(url: str, waarde: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"value": waarde}, request=httpx.Request("GET", url))


def zet_klaar(monkeypatch, aanpassen: Callable[[dict], None] | None = None) -> list[dict]:
    """Vervang de bron; geeft de lijst met de params van elke aanroep van TypedDataSet terug."""
    from onderwijsbronnen.cbs import client

    from data import vacatures_ontstaan

    bron = opname()
    if aanpassen:
        bron = copy.deepcopy(bron)
        aanpassen(bron)
    aanroepen: list[dict] = []
    eerder = client.httpx

    def get(url, params=None, timeout=None, **kwargs):
        if "/85081NED/" not in url:
            return eerder.get(url, params=params, timeout=timeout, **kwargs)
        params = dict(params or {})
        deel = url.rstrip("/").split("/")[-1]
        if deel == "TypedDataSet":
            assert params.get("$filter") == FILTER, params
            aanroepen.append(params)
            rijen = bron["TypedDataSet"]
            skip, top = int(params.get("$skip", 0)), int(params.get("$top", 10000))
            return _antwoord(url, rijen[skip : skip + top])
        return _antwoord(url, bron[deel])

    monkeypatch.setattr(client, "httpx", SimpleNamespace(get=get))
    vacatures_ontstaan._tabel.cache_clear()
    return aanroepen

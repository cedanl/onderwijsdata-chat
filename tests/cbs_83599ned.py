"""Het opgenomen antwoord van CBS 83599NED (`tests/fixtures/cbs/83599NED_provincies.json`) als nagebootste OData-bron.

`zet_klaar` vervangt `httpx` in de CBS-client van onderwijsbronnen: de lader (data/vacatures_cbs.py) gaat zo door de
echte client, met haar `$filter`, paginering en het wegknippen van de spaties in de sleutels, maar zonder netwerk.
`aanpassen` wijzigt een kopie van het antwoord (een lege cel, een ontbrekende rij) voordat de bron het geeft. De
cache van de lader leegt `zet_klaar` vooraf; de fixture `cbs_vacatures` (tests/conftest.py) ook achteraf.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import httpx

PAD = Path(__file__).parent / "fixtures" / "cbs" / "83599NED_provincies.json"
FILTER = "substringof('PV',RegioS)"


def opname() -> dict:
    return json.loads(PAD.read_text(encoding="utf-8"))


def _antwoord(url: str, waarde: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"value": waarde}, request=httpx.Request("GET", url))


def zet_klaar(monkeypatch, aanpassen: Callable[[dict], None] | None = None) -> list[dict]:
    """Vervang de bron; geeft de lijst met de params van elke aanroep van TypedDataSet terug."""
    from onderwijsbronnen.cbs import client

    from data import vacatures_cbs

    bron = opname()
    if aanpassen:
        bron = copy.deepcopy(bron)
        aanpassen(bron)
    aanroepen: list[dict] = []

    def get(url, params=None, timeout=None, **_):
        params = dict(params or {})
        deel = url.rstrip("/").split("/")[-1]
        assert "/83599NED/" in url, url
        if deel == "TypedDataSet":
            assert params.get("$filter") == FILTER, params
            aanroepen.append(params)
            rijen = bron["TypedDataSet"]
            skip, top = int(params.get("$skip", 0)), int(params.get("$top", 10000))
            return _antwoord(url, rijen[skip : skip + top])
        return _antwoord(url, bron[deel])

    monkeypatch.setattr(client, "httpx", SimpleNamespace(get=get))
    vacatures_cbs._tabel.cache_clear()
    return aanroepen

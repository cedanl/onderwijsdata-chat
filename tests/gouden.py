"""De bevroren bronnen onder de gouden tests van de rekenende tools (#870), zonder netwerk.

`scripts/gouden_testfixtures.py` haalde de bestanden één keer live op en schreef ze naar `tests/fixtures/gouden/`;
`bronnen.json` noemt per bestand de bron-URL, het filter en de ophaaldatum. Deze module zet ze op de plek waar de tools
hun bron laden, zo laag mogelijk, zodat het rekenwerk van de tools zelf getest wordt:

- DUO: `onderwijsbronnen.duo.load` (zoals de fixture `duo_fixtures`, waar de rest vandaan komt: het instellingenregister);
- CBS: `tools.cbs.definitions`, `tools.cbs.get` en `tools.cbs.data`, die laatste filtert als CBS (`tests/cbs_feed.py`);
- de mbo-indicatoren en de Inspectie (bg en po-so-vo): een httpx-client die alleen het bevroren bestand op de bron-URL
  kent;
- UWV en ROA: `data.arbeidsmarkt._uwv` en `_roa`.

Het netwerk is dicht via het netwerkblok van alle tests (`tests/netwerkblok.py`, #915): een tool die toch naar
buiten gaat, breekt de test.
"""

from __future__ import annotations

import json
from functools import cache

import httpx
import pandas as pd

from scripts import gouden_testfixtures as g
from tests.cbs_feed import maak_feed

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ODS = "application/vnd.oasis.opendocument.spreadsheet"


class NetwerkInGoudenTest(AssertionError):
    """Een gouden test vroeg een URL waarvoor geen bevroren bestand is: de fixture dekt de bron niet."""


@cache
def bronnen() -> dict[str, dict]:
    return json.loads(g.BRONNEN.read_text())


def _duo(monkeypatch) -> None:
    from onderwijsbronnen import duo

    terugval = duo.load  # de DUO-fixtures van #766, voor het register en de adressen
    tekst = json.loads(g.TEKSTKOLOMMEN.read_text())

    def load(dataset_id: str, resource: int = 0, **kwargs) -> pd.DataFrame:
        naam = g.duo_bestand(dataset_id, resource)
        if naam not in tekst:
            return terugval(dataset_id, resource, **kwargs)
        df = pd.read_csv(g.MAP / naam, dtype=dict.fromkeys(tekst[naam], str))
        # Zoals riodata: de herkomst van het bestand, waar het peilmoment van de store uit komt.
        df.attrs["bron"] = {"dataset_id": dataset_id, "url": bronnen()[naam]["url"],
                            "last_modified": bronnen()[naam]["bijgewerkt"]}  # fmt: skip
        return df

    monkeypatch.setattr(duo, "load", load)


def _cbs(monkeypatch) -> None:
    import tools.cbs

    opnames = {dataset_id: g.lees_json_gz(g.cbs_bestand(dataset_id)) for dataset_id in g.CBS_AANROEPEN}
    feeds = {dataset_id: maak_feed(opname["rijen"]) for dataset_id, opname in opnames.items()}
    monkeypatch.setattr(tools.cbs, "definitions", lambda dataset_id: opnames[dataset_id]["definitions"])
    monkeypatch.setattr(
        tools.cbs, "get", lambda dataset_id, endpoint, **params: opnames[dataset_id]["get"].get(endpoint, [])
    )
    monkeypatch.setattr(tools.cbs, "data", lambda dataset_id, **params: feeds[dataset_id](dataset_id, **params))


def client(bestanden: dict[str, tuple[bytes, str]]) -> httpx.Client:
    """Een httpx-client die per URL het bevroren bestand (inhoud, content-type) geeft en elke andere URL weigert."""

    def antwoord(request: httpx.Request) -> httpx.Response:
        if (bestand := bestanden.get(str(request.url))) is None:
            raise NetwerkInGoudenTest(f"geen fixture voor {request.url}")
        inhoud, soort = bestand
        return httpx.Response(200, content=inhoud, headers={"content-type": soort})

    return httpx.Client(transport=httpx.MockTransport(antwoord))


def _mbo_indicatoren(monkeypatch) -> None:
    from tools import mbo_indicatoren as m

    bron = bronnen()[g.MBO_INDICATOREN]
    # De pagina met de edities is niet bevroren: alleen de keuze van de editie, het bestand zelf wel.
    monkeypatch.setattr(m, "nieuwste_editie", lambda pagina: (bron["editie"], bron["url"], bron["peildatum"]))
    bestanden = {m.PAGINA: (b"", "text/html"), bron["url"]: ((g.MAP / g.MBO_INDICATOREN).read_bytes(), _XLSX)}
    monkeypatch.setattr(m, "editie", lambda: m.haal_editie(client(bestanden)))


def _inspectie(monkeypatch) -> None:
    from tools import inspectie

    url = bronnen()[g.INSPECTIE]["url"]
    inhoud = (g.MAP / g.INSPECTIE).read_bytes()
    # De drie pagina's naar het bestand zijn niet bevroren; het bg-bestand zelf wel.
    monkeypatch.setattr(inspectie, "_bg_url", lambda client: url)
    monkeypatch.setattr(inspectie, "peilbestand", lambda: inspectie.haal_peilbestand(client({url: (inhoud, _ODS)})))


def _inspectie_vo(monkeypatch) -> None:
    from tools import inspectie_vo

    url = bronnen()[g.INSPECTIE_VO]["url"]
    inhoud = (g.MAP / g.INSPECTIE_VO).read_bytes()
    # Zoals het bg-bestand: de pagina's niet bevroren, het po-so-vo-bestand wel. De vo-vestigingen komen via `_duo`.
    monkeypatch.setattr(inspectie_vo, "_po_so_vo_url", lambda client: url)
    monkeypatch.setattr(
        inspectie_vo, "peilbestand", lambda: inspectie_vo.haal_peilbestand_vo(client({url: (inhoud, _ODS)}))
    )


def _arbeidsmarkt(monkeypatch) -> None:
    from data import arbeidsmarkt

    uwv = pd.read_csv(g.MAP / g.UWV, dtype={"PEILDATUM": str})
    roa = pd.read_csv(g.MAP / g.ROA, dtype={"versie": str})
    monkeypatch.setattr(arbeidsmarkt, "_uwv", lambda: uwv.copy())
    monkeypatch.setattr(arbeidsmarkt, "_roa", lambda: roa.copy())


def wis_caches() -> None:
    import tools.cbs
    from tools import inspectie_vo

    inspectie_vo._vestigingen_van.cache_clear()

    tools.cbs._dimension_rows.cache_clear()
    tools.cbs._tabelbeschrijving.cache_clear()


def zet_klaar(monkeypatch) -> None:
    """Alle bevroren bronnen op hun plek; het netwerk is al dicht (`tests/netwerkblok.py`)."""
    _duo(monkeypatch)
    _cbs(monkeypatch)
    _mbo_indicatoren(monkeypatch)
    _inspectie(monkeypatch)
    _inspectie_vo(monkeypatch)
    _arbeidsmarkt(monkeypatch)
    wis_caches()

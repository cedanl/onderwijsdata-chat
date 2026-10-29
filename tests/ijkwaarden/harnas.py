"""IJkwaarden voor de bronwaarheid-evals (#190): rechtstreeks uit CBS, DUO en RIO, zonder LLM en zonder tools/.

De evals in tests/e2e/evaluations.json verwijzen per referentiewaarde naar een id van hier
(`data_points.ijkwaarden`); tests/e2e/ijkwaarden.json is de vastgelegde stand, met per waarde de
bron, de selectie, de eenheid, het schooljaar, de CBS-status en de dag van ophalen. Het script
scripts/ijkwaarden.py haalt alles opnieuw op en toont elk verschil met de vastgelegde stand.
Vastleggen is een expliciete stap (--schrijf): drift van de bron wordt zichtbaar, in plaats van
dat een eval stil gaat falen of stil een nieuwe waarde overneemt.

Bewust niet via tools/: een fout in de tools mag de ijkwaarde niet mee veranderen. CBS gaat via
httpx op de OData-feed, DUO en RIO via het riodata-package. De DUO-regel voor -1 (onderdrukte cel:
niet meetellen, de som is een ondergrens) staat hier opnieuw uitgeschreven, met opzet.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).resolve().parent.parent / "e2e" / "ijkwaarden.json"

CBS_ODATA = "https://opendata.cbs.nl/ODataApi/odata"
DUO_SENTINEL = -1  # DUO publiceert een onderdrukte cel (1-4) als -1
RIO_INSTELLING = "ERKENDE_ONDERWIJSINSTELLING"
RIO_HIERARCHISCH = "HIERARCHISCH"

# Vaste codes van 85423NED (hbo en wo), uit de dimensies van de tabel.
_HBO, _WO = "A025294", "A025297"
_VOLTIJD, _ALLE_VORMEN = "A028666", "T001228"
_ALLE_FASEN, _ALLE_GESLACHTEN, _VROUWEN = "A045745", "T001038", "4000"
# Vaste codes van 85353NED (mbo): niveau, leerweg, studierichting en regio op hun totaal.
_MBO_TOTALEN = {"Niveau": "T001336", "Leerweg": "A025290", "Studierichting": "T001072", "Regio": "NL01"}
# Vaste codes van 85354NED (mbo-studenten landelijk, #805): elke dimensie op haar totaal, leerweg incl. extranei.
_MBO_STUDENTEN = {
    "Geslacht": "T001038",
    "Niveau": "T001336",
    "Leerweg": "A025290",
    "Herkomstland": "T001040",
    "GeboortelandOuders": "T001638",
}
_EXCL_EXTRANEI = "A041867"
_HU = "25DW"


@dataclass(frozen=True)
class Ijkpunt:
    """Eén referentiewaarde: wat ze meet en precies welke selectie bij de bron haar geeft."""

    id: str
    bron: str  # cbs | duo | rio
    omschrijving: str
    eenheid: str
    selectie: dict[str, Any]
    schooljaar: str | None = None


def _cbs(id: str, omschrijving: str, dataset: str, dimensies: dict[str, str], periode: str, schooljaar: str) -> Ijkpunt:
    selectie = {"dataset": dataset, "dimensies": dimensies, "periode": periode, "onderwerp": _ONDERWERP[dataset]}
    return Ijkpunt(id, "cbs", omschrijving, "studenten (CBS, afgerond op 10-tallen)", selectie, schooljaar)


def _duo(id: str, omschrijving: str, dataset: str, kolom: str, eenheid: str, vorm: str, jaar: int) -> Ijkpunt:
    selectie = {
        "dataset": dataset,
        "resource": 3,  # het bestand met OPLEIDINGSVORM
        "instelling": _HU,
        "opleidingsvorm": vorm,
        "studiejaar": jaar,
        "kolom": kolom,
    }
    return Ijkpunt(id, "duo", omschrijving, eenheid, selectie, f"{jaar}/{(jaar + 1) % 100:02d}")


_ONDERWERP = {"85423NED": "TotaalIngeschrevenen_1", "85353NED": "MboStudenten_1", "85354NED": "MboStudenten_1"}
_HBO_VT = {
    "Onderwijssoort": _HBO,
    "Opleidingsvorm": _VOLTIJD,
    "Opleidingsfase": _ALLE_FASEN,
    "Geslacht": _ALLE_GESLACHTEN,
}
_PERSONEN = "personen (hoofdinschrijvingen, p01hoinges)"
_INSCHRIJVINGEN = "inschrijvingen (p03hoinschr)"
_EERSTEJAARS = "eerstejaars personen (p02ho1ejrs)"

IJKPUNTEN: tuple[Ijkpunt, ...] = (
    _cbs("cbs-hbo-voltijd-2024", "hbo voltijd landelijk 2024/25", "85423NED", _HBO_VT, "2024SJ00", "2024/25"),
    _cbs("cbs-hbo-voltijd-2025", "hbo voltijd landelijk 2025/26", "85423NED", _HBO_VT, "2025SJ00", "2025/26"),
    _cbs(
        "cbs-hbo-totaal-2024",
        "hbo alle opleidingsvormen landelijk 2024/25",
        "85423NED",
        {**_HBO_VT, "Opleidingsvorm": _ALLE_VORMEN},
        "2024SJ00",
        "2024/25",
    ),
    _cbs(
        "cbs-wo-totaal-2024",
        "wo alle opleidingsvormen landelijk 2024/25",
        "85423NED",
        {**_HBO_VT, "Onderwijssoort": _WO, "Opleidingsvorm": _ALLE_VORMEN},
        "2024SJ00",
        "2024/25",
    ),
    _cbs(
        "cbs-mbo-vrouwen-2021",
        "mbo vrouwen landelijk 2021/22 (F-10, #531)",
        "85353NED",
        {**_MBO_TOTALEN, "Geslacht": _VROUWEN},
        "2021SJ00",
        "2021/22",
    ),
    _cbs(
        "cbs-mbo-vrouwen-2024",
        "mbo vrouwen landelijk 2024/25 (F-10, #531)",
        "85353NED",
        {**_MBO_TOTALEN, "Geslacht": _VROUWEN},
        "2024SJ00",
        "2024/25",
    ),
    _cbs(
        "cbs-mbo-totaal-2024",
        "mbo-studenten landelijk 2024/25 (#805)",
        "85354NED",
        _MBO_STUDENTEN,
        "2024SJ00",
        "2024/25",
    ),
    _cbs(
        "cbs-mbo-totaal-excl-extranei-2024",
        "mbo-studenten landelijk zonder extranei 2024/25 (#805)",
        "85354NED",
        {**_MBO_STUDENTEN, "Leerweg": _EXCL_EXTRANEI},
        "2024SJ00",
        "2024/25",
    ),
    *(
        _duo(
            f"duo-hu-voltijd-{jaar}",
            f"HU voltijd {jaar}/{(jaar + 1) % 100:02d}",
            "p01hoinges",
            "AANTAL_INGESCHREVENEN",
            _PERSONEN,
            "VT",
            jaar,
        )
        for jaar in range(2021, 2026)
    ),
    _duo("duo-hu-deeltijd-2024", "HU deeltijd 2024/25", "p01hoinges", "AANTAL_INGESCHREVENEN", _PERSONEN, "DT", 2024),
    _duo("duo-hu-deeltijd-2025", "HU deeltijd 2025/26", "p01hoinges", "AANTAL_INGESCHREVENEN", _PERSONEN, "DT", 2025),
    *(
        _duo(
            f"duo-hu-inschrijvingen-voltijd-{jaar}",
            f"HU voltijd inschrijvingen {jaar}/{(jaar + 1) % 100:02d}",
            "p03hoinschr",
            "AANTAL_INSCHRIJVINGEN",
            _INSCHRIJVINGEN,
            "VT",
            jaar,
        )
        for jaar in range(2021, 2026)
    ),
    _duo(
        "duo-hu-eerstejaars-voltijd-2021",
        "HU voltijd eerstejaars 2021/22",
        "p02ho1ejrs",
        "AANTAL_EERSTEJAARS_INGESCHREVENEN",
        _EERSTEJAARS,
        "VT",
        2021,
    ),
    _duo(
        "duo-hu-eerstejaars-voltijd-2025",
        "HU voltijd eerstejaars 2025/26",
        "p02ho1ejrs",
        "AANTAL_EERSTEJAARS_INGESCHREVENEN",
        _EERSTEJAARS,
        "VT",
        2025,
    ),
    Ijkpunt(
        "rio-aeres-hogeschool",
        "rio",
        "Aeres Hogeschool: instellingscode en vestigingen",
        "code en vestigingsplaatsen",
        {"resource": "erkenningen", "volledigeNaam": "Aeres Hogeschool", "type": RIO_INSTELLING},
    ),
)


# --- ophalen bij de bron --------------------------------------------------------------


def _cbs_get(dataset: str, pad: str, **params) -> list[dict]:
    import httpx

    r = httpx.get(f"{CBS_ODATA}/{dataset}/{pad}", params=params, timeout=60, follow_redirects=True)
    r.raise_for_status()
    return r.json()["value"]


@cache
def _cbs_perioden(dataset: str) -> dict[str, str]:
    return {r["Key"].strip(): (r.get("Status") or "").strip() for r in _cbs_get(dataset, "Perioden")}


@cache
def _cbs_gewijzigd(dataset: str) -> str | None:
    rows = _cbs_get(dataset, "TableInfos")
    gewijzigd = rows[0].get("Modified") if rows else None
    return gewijzigd[:10] if isinstance(gewijzigd, str) else None


def cbs_filter(dimensies: dict[str, str], periode: str) -> str:
    """De OData-filter: `trim()` omdat CBS de sleutels van een dimensie opvult tot één breedte (#531)."""
    delen = [f"trim({dim}) eq '{code}'" for dim, code in sorted(dimensies.items())]
    return " and ".join([*delen, f"trim(Perioden) eq '{periode}'"])


def cbs_url(selectie: dict[str, Any]) -> str:
    from urllib.parse import urlencode

    query = urlencode(
        {"$filter": cbs_filter(selectie["dimensies"], selectie["periode"]), "$select": selectie["onderwerp"]}
    )
    return f"{CBS_ODATA}/{selectie['dataset']}/TypedDataSet?{query}"


def haal_cbs(punt: Ijkpunt) -> dict[str, Any]:
    s = punt.selectie
    rows = _cbs_get(
        s["dataset"], "TypedDataSet", **{"$filter": cbs_filter(s["dimensies"], s["periode"]), "$select": s["onderwerp"]}
    )
    if len(rows) != 1:
        raise ValueError(f"{punt.id}: {len(rows)} rijen bij CBS, één verwacht")
    return {
        "waarde": rows[0][s["onderwerp"]],
        "status": _cbs_perioden(s["dataset"]).get(s["periode"]),
        "bron_gewijzigd": _cbs_gewijzigd(s["dataset"]),
        "url": cbs_url(s),
    }


@cache
def _duo_bestand(dataset: str, resource: int):
    from riodata import duo

    return duo.load(dataset, resource)


def duo_som(df, selectie: dict[str, Any]) -> tuple[int, int]:
    """(som, onderdrukte cellen) van de kolom over de rijen van instelling, opleidingsvorm en studiejaar.

    Een -1 is een onderdrukte cel en telt niet mee: de som is dan een ondergrens, en het
    aantal zulke cellen staat bij de ijkwaarde.
    """
    import pandas as pd

    rijen = df[
        (df["INSTELLINGSCODE_ACTUEEL"].astype(str).str.strip() == selectie["instelling"])
        & (df["OPLEIDINGSVORM"].astype(str).str.strip().str.upper() == selectie["opleidingsvorm"])
        & (pd.to_numeric(df["STUDIEJAAR"], errors="coerce") == selectie["studiejaar"])
    ]
    waarden = pd.to_numeric(rijen[selectie["kolom"]], errors="coerce")
    onderdrukt = int((waarden == DUO_SENTINEL).sum())
    return int(waarden[waarden != DUO_SENTINEL].sum()), onderdrukt


def haal_duo(punt: Ijkpunt) -> dict[str, Any]:
    s = punt.selectie
    som, onderdrukt = duo_som(_duo_bestand(s["dataset"], s["resource"]), s)
    return {
        "waarde": som,
        "onderdrukte_cellen": onderdrukt,
        "url": f"https://onderwijsdata.duo.nl/datasets/{s['dataset']}",
    }


def vestigingsplaats(volledige_naam: str) -> str:
    """RIO zet de plaats achter de naam: 'Aeres Hogeschool; Ede' → 'Ede'."""
    naam = " ".join(str(volledige_naam).split())
    return naam.rsplit(";", 1)[-1].strip() if ";" in naam else naam


def haal_rio(punt: Ijkpunt) -> dict[str, Any]:
    from riodata import fetch, get, related

    s = punt.selectie
    vandaag = date.today().isoformat()
    # RIO LOD API v3: het typefilter heet `type`; v2 (erkenningtype) is op 19-10-2026 verwijderd (#627).
    gevonden = fetch(s["resource"], volledigeNaam=s["volledigeNaam"], type=s["type"], datumGeldigOp=vandaag)
    codes = sorted({e["code"] for e in gevonden if e.get("type") == s["type"] and not e.get("einddatum")})
    if len(codes) != 1:
        raise ValueError(f"{punt.id}: {len(codes)} instellingen bij RIO voor {s['volledigeNaam']!r}: {codes}")
    code = codes[0]
    relaties = related(s["resource"], code, "instellingsrelaties")
    onder = sorted(
        {
            str(r["naarErkenningId"])
            for r in relaties
            if r.get("soort") == RIO_HIERARCHISCH and str(r["vanErkenningId"]) == code and not r.get("einddatum")
        }
    )
    vestigingen = {c: vestigingsplaats(get(s["resource"], c).get("volledigeNaam", "")) for c in onder}
    return {
        "waarde": {"code": code, "vestigingen": vestigingen},
        "url": f"https://lod.onderwijsregistratie.nl/api/rio/v3/erkenningen/{code}",
    }


_HALERS: dict[str, Callable[[Ijkpunt], dict[str, Any]]] = {"cbs": haal_cbs, "duo": haal_duo, "rio": haal_rio}


def haal(punt: Ijkpunt) -> dict[str, Any]:
    """De ijkwaarde zoals de bron haar nu geeft, met wat de fixture over haar vastlegt."""
    kern = {k: v for k, v in asdict(punt).items() if k != "id"}
    return {**kern, **_HALERS[punt.bron](punt)}


def haal_alles(bronnen: set[str] | None = None) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Elke ijkwaarde die de bron geeft, plus per ijkpunt de fout van wie niet antwoordde (#627).

    Eén bron die faalt (RIO gaf op 19-10 HTTP 410) mag het rapport over CBS en DUO niet blokkeren: de
    aanroeper ziet in `fouten` wat ontbreekt en beslist of dat telt.
    """
    live: dict[str, dict[str, Any]] = {}
    fouten: dict[str, str] = {}
    for punt in IJKPUNTEN:
        if bronnen is not None and punt.bron not in bronnen:
            continue
        try:
            live[punt.id] = haal(punt)
        except Exception as fout:  # een bron die niet antwoordt is een meetfout, geen nieuwe stand
            fouten[punt.id] = f"{type(fout).__name__}: {fout}"
    return live, fouten


# --- vergelijken en vastleggen ---------------------------------------------------------

_VERGELEKEN = ("waarde", "status", "onderdrukte_cellen")


@dataclass(frozen=True)
class Verschil:
    id: str
    soort: str  # afwijking | nieuw | verdwenen
    vastgelegd: Any = None
    live: Any = None
    veld: str | None = None


def vergelijk(vastgelegd: dict[str, dict], live: dict[str, dict]) -> list[Verschil]:
    """Elk verschil tussen de vastgelegde stand en de bron: waarde, status en onderdrukte cellen.

    De dag van ophalen en de datum van de bron tellen niet: die wijzigen zonder dat de waarde wijzigt.
    """
    uit: list[Verschil] = []
    for id in sorted(set(vastgelegd) | set(live)):
        if id not in live:
            uit.append(Verschil(id, "verdwenen", vastgelegd=vastgelegd[id].get("waarde")))
        elif id not in vastgelegd:
            uit.append(Verschil(id, "nieuw", live=live[id].get("waarde")))
        else:
            for veld in _VERGELEKEN:
                oud, nieuw = vastgelegd[id].get(veld), live[id].get(veld)
                if oud != nieuw:
                    uit.append(Verschil(id, "afwijking", oud, nieuw, veld))
    return uit


def lees(pad: Path = FIXTURE) -> dict[str, Any]:
    return json.loads(pad.read_text(encoding="utf-8"))


def schrijf(waarden: dict[str, dict[str, Any]], pad: Path = FIXTURE, vandaag: date | None = None) -> None:
    inhoud = {
        "_doc": (
            "Vastgelegde ijkwaarden voor de bronwaarheid-evals (#190), rechtstreeks bij CBS, DUO en RIO opgehaald "
            "door scripts/ijkwaarden.py; niet met de hand bewerken. evaluations.json verwijst per referentiewaarde "
            "naar een id hier (data_points.ijkwaarden). `python scripts/ijkwaarden.py` toont elk verschil met de bron; "
            "`--schrijf` legt de nieuwe stand vast."
        ),
        "opgehaald_op": (vandaag or date.today()).isoformat(),
        "waarden": {id: waarden[id] for id in sorted(waarden)},
    }
    pad.write_text(json.dumps(inhoud, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def regel(v: Verschil) -> str:
    if v.soort == "afwijking":
        return f"  ✗ {v.id:<36} {v.veld}: vastgelegd {v.vastgelegd!r} → bron {v.live!r}"
    if v.soort == "nieuw":
        return f"  + {v.id:<36} nieuw: {v.live!r}"
    return f"  - {v.id:<36} niet meer in de lijst (vastgelegd {v.vastgelegd!r})"

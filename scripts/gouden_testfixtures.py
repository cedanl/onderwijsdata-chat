"""Ververs de bevroren bronbestanden onder de gouden tests van de rekenende tools (#870).

De rekenende tools (get_mbo_indicatoren, get_accreditatie, get_inspectieoordeel, de recepten van get_maat, de
UWV/ROA-tools en compute_kpi) werden alleen op vorm getest: een verschoven kolom of een verkeerde noemer viel pas op in
een handmatige eval. Dit script haalt hun bronnen één keer live op, houdt alleen de rijen over die de gouden tests
gebruiken en schrijft ze naar `tests/fixtures/gouden/`, met per bestand de bron-URL en de ophaaldatum in
`bronnen.json`. `tests/gouden.py` leest ze in plaats van het netwerk; de tests staan in `tests/test_gouden_*.py`.

    .venv/bin/python scripts/gouden_testfixtures.py

Zelfde aanpak als `scripts/duo_testfixtures.py`, met een eigen map: wie de DUO-fixtures van de dashboards ververst,
verschuift hiermee niet ongemerkt de gouden getallen. Na verversen veranderen die getallen meestal wel; reken ze dan
opnieuw na met pandas op de nieuwe bestanden (de berekening staat bij elke test) en commit bestanden en tests samen.
"""

from __future__ import annotations

import gzip
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import duo_testfixtures

MAP = ROOT / "tests" / "fixtures" / "gouden"
BRONNEN = MAP / "bronnen.json"
TEKSTKOLOMMEN = MAP / "tekstkolommen.json"

# De instellingen van de gouden tests. Bewust niet de Hogeschool Utrecht: die heeft de live ijkwaarden van #190.
UU = "21PD"  # Universiteit Utrecht: de ho-recepten, accreditatie en de KPI-reeks
MONDRIAAN = "27GZ"  # ROC Mondriaan: mbo-studenten per instelling en de mbo-indicatoren
INSPECTIE_INSTELLINGEN = {
    "25LH": 40597,  # ROC Midden Nederland: alleen mbo
    "23JA": 67237,  # Grafisch Lyceum Rotterdam: bestuur met vo en mbo (gemengd)
}
UWV_PROVINCIE = "Flevoland"  # de kleinste provincie in rijen, zodat het bestand klein blijft
UWV_KOLOMMEN = ["PEILDATUM", "PROVINCIE", "GEMEENTE", "BEROEPENCLUSTER", "AANTAL"]
ROA_KOLOMMEN = ["regionaam", "thema", "aggregatieniveau", "detailniveau", "onderwerp", "perc", "aantal", "typering",
                "versie"]  # fmt: skip

# DUO: (dataset, resource) → (kolom met de instellingscode, de codes die blijven). Het register van de app leest zijn
# mbo-instellingen uit mbo-studenten-per-instelling: dat bestand houdt de mbo-instellingen van de DUO-fixtures, anders
# kent het register in de gouden tests alleen ROC Mondriaan.
DUO: dict[tuple[str, int], tuple[str, set[str]]] = {
    ("p01hoinges", 4): ("INSTELLINGSCODE_ACTUEEL", {UU}),
    ("p02ho1ejrs", 4): ("INSTELLINGSCODE_ACTUEEL", {UU}),
    ("p03hoinschr", 4): ("INSTELLINGSCODE_ACTUEEL", {UU}),
    ("mbo-studenten-per-instelling", 0): ("INSTELLINGSCODE", {MONDRIAAN, *duo_testfixtures.MBO}),
    ("overzicht-erkenningen-ho", 0): ("INSTELLINGSCODE", {UU}),
}

# CBS: de landelijke recepten van get_maat, met de afbakeningen die de tests vragen.
CBS_AANROEPEN: dict[str, list[dict[str, Any]]] = {
    "85423NED": [{"maat": "deelnemers_ho_landelijk", "sector": s, "vorm": v} for s in ("hbo", "wo") for v in
                 ("alle", "voltijd")],
    "85354NED": [{"maat": "mbo_studenten_landelijk", "vorm": v} for v in ("alle", "bol", "bbl")],
    "85569NED": [{"maat": "doorstroom_vmbo_mbo"}],
}  # fmt: skip

MBO_INDICATOREN = "mbo-indicatoren.xlsx"
INSPECTIE = "inspectie-bg.ods"
UWV = "uwv-vacatures.csv.gz"
ROA = "roa-ais2030.csv.gz"


def duo_bestand(dataset_id: str, resource: int) -> str:
    return f"duo-{dataset_id}_{resource}.csv.gz"


def cbs_bestand(dataset_id: str) -> str:
    return f"cbs-{dataset_id}.json.gz"


def _csv(df, naam: str) -> None:
    # mtime 0: dezelfde bron geeft hetzelfde bestand, dus geen lege diff bij verversen.
    df.to_csv(MAP / naam, index=False, compression={"method": "gzip", "mtime": 0})


def _json_gz(waarde, naam: str) -> None:
    tekst = json.dumps(waarde, ensure_ascii=False, sort_keys=True, indent=0, default=str)
    (MAP / naam).write_bytes(gzip.compress(tekst.encode(), mtime=0))


def lees_json_gz(naam: str):
    return json.loads(gzip.decompress((MAP / naam).read_bytes()))


def _duo(bronnen: dict, tekst: dict) -> None:
    import pandas as pd
    from riodata import duo

    for (dataset_id, resource), (kolom, codes) in DUO.items():
        df = duo.load(dataset_id, resource)
        bron = df.attrs.get("bron") or {}
        df = df[df[kolom].astype(str).str.strip().isin(codes)]
        naam = duo_bestand(dataset_id, resource)
        _csv(df, naam)
        tekst[naam] = [k for k in df.columns if not pd.api.types.is_numeric_dtype(df[k])]
        bronnen[naam] = {"url": bron.get("url"), "bijgewerkt": bron.get("last_modified"), "filter": f"{kolom} in {sorted(codes)}",
                         "rijen": len(df)}  # fmt: skip


def _mbo_indicatoren(bronnen: dict) -> None:
    import httpx

    from tools import mbo_indicatoren as m

    with httpx.Client(headers=m._HEADERS, timeout=m._TIMEOUT_S, follow_redirects=True) as client:
        jaar, url, peildatum = m.nieuwste_editie(client.get(m.PAGINA).text)
        inhoud = m._xlsx(client.get(url))
    m.lees_xlsx(inhoud)  # leest het bestand niet, dan geen fixture
    # Het hele bestand (48 kB): de koprijen en de swap-controle per groep horen bij wat getest wordt.
    (MAP / MBO_INDICATOREN).write_bytes(inhoud)
    bronnen[MBO_INDICATOREN] = {"url": url, "editie": jaar, "peildatum": peildatum, "filter": "geen"}


def _ods_met_rijen(inhoud: bytes, houden) -> tuple[bytes, int]:
    """Het ODS-bestand met alleen de kop en de rijen waarvoor `houden(rij)` waar is, verder byte voor byte gelijk."""
    from tools import inspectie as i

    tabel = i._ODS_TABEL
    with zipfile.ZipFile(io.BytesIO(inhoud)) as z:
        bestanden = {n: z.read(n) for n in z.namelist()}
    for prefix, uri in (("office", i._ODS_OFFICE), ("table", tabel), ("text", i._ODS_TEKST.removesuffix("p"))):
        ElementTree.register_namespace(prefix, uri.strip("{}"))
    wortel = ElementTree.fromstring(bestanden["content.xml"])
    blad = next(wortel.iter(tabel + "table"))
    rijen = [r for r in blad if r.tag == tabel + "table-row"]
    kop = [i._cel(c) for c in rijen[0]]
    gehouden = 0
    for rij in rijen[1:]:
        waarden = [i._cel(c) for c in rij]
        if houden(dict(zip(kop, waarden, strict=False))):
            gehouden += 1
        else:
            blad.remove(rij)
    bestanden["content.xml"] = ElementTree.tostring(wortel, xml_declaration=True, encoding="UTF-8")
    uit = io.BytesIO()
    with zipfile.ZipFile(uit, "w") as z:
        # Het mimetype eerst en ongecomprimeerd, zoals ODF het wil; de rest gecomprimeerd, met een vaste datum.
        for naam, data in sorted(bestanden.items(), key=lambda kv: kv[0] != "mimetype"):
            info = zipfile.ZipInfo(naam, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED if naam == "mimetype" else zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return uit.getvalue(), gehouden


def _inspectie(bronnen: dict) -> None:
    import httpx

    from tools import inspectie as i

    with httpx.Client(headers=i._HEADERS, timeout=i._TIMEOUT_S, follow_redirects=True) as client:
        url = i._bg_url(client)
        inhoud = i._haal(client, url).content
    besturen = set(INSPECTIE_INSTELLINGEN.values())
    klein, gehouden = _ods_met_rijen(inhoud, lambda rij: i.bestuursnummer(rij.get("Bestuursnummer")) in besturen)
    (MAP / INSPECTIE).write_bytes(klein)
    bronnen[INSPECTIE] = {"url": url, "filter": f"Bestuursnummer in {sorted(besturen)}", "rijen": gehouden}


def _cbs(bronnen: dict) -> None:
    from unittest.mock import patch

    import tools.cbs
    from tools import maten

    for dataset_id, aanroepen in CBS_AANROEPEN.items():
        opname: dict = {"definitions": None, "get": {}, "rijen": []}
        echt = (tools.cbs.definitions, tools.cbs.get, tools.cbs.data)

        def definitions(ds, _echt=echt[0], _opname=opname):
            _opname["definitions"] = _echt(ds)
            return _opname["definitions"]

        def get(ds, endpoint, _echt=echt[1], _opname=opname, **params):
            assert not params, params  # labels en TableInfos: hele endpoints, geen selectie
            _opname["get"][endpoint] = _echt(ds, endpoint)
            return _opname["get"][endpoint]

        def data(ds, _echt=echt[2], _opname=opname, **params):
            rijen = _echt(ds, **params)
            _opname["rijen"] += [r for r in rijen if r not in _opname["rijen"]]
            return rijen

        tools.cbs._dimension_rows.cache_clear()
        tools.cbs._tabelbeschrijving.cache_clear()
        with (
            patch("tools.cbs.definitions", definitions),
            patch("tools.cbs.get", get),
            patch("tools.cbs.data", data),
        ):
            for aanroep in aanroepen:
                uit = json.loads(maten.get_maat(**aanroep))
                assert "data_key" in uit, uit
        _json_gz(opname, cbs_bestand(dataset_id))
        bronnen[cbs_bestand(dataset_id)] = {
            "url": f"https://opendata.cbs.nl/ODataApi/odata/{dataset_id}",
            "filter": "de rijen die get_maat opvraagt bij " + "; ".join(json.dumps(a) for a in aanroepen),
            "rijen": len(opname["rijen"]),
        }


def _uwv(bronnen: dict) -> None:
    from riodata import uwv

    df = uwv.load("latest", rec_type="Vacature")
    df = df.loc[df["PROVINCIE"] == UWV_PROVINCIE, UWV_KOLOMMEN]
    _csv(df, UWV)
    bronnen[UWV] = {"url": "riodata uwv.load('latest', rec_type='Vacature') (UWV Open Match)",
                    "filter": f"PROVINCIE = {UWV_PROVINCIE}; kolommen {', '.join(UWV_KOLOMMEN)}", "rijen": len(df)}  # fmt: skip


def _roa(bronnen: dict) -> None:
    from riodata import roa

    from data import arbeidsmarkt as a

    df = roa.load("ais2030", "arbeidsmarkt")
    niveaus = [n for ns in a.ROA_NIVEAUS.values() for n in ns]
    df = df.loc[
        (df["regionaam"] == a.ROA_LANDELIJK)
        & (df["aggregatieniveau"] == a._ROA_NIVEAU)
        & df["detailniveau"].isin(niveaus)
        & df["thema"].isin([a._ROA_SIS, a._ROA_PROGNOSE])
        & df["onderwerp"].isin([*a.ROA_SIS_INDICATOREN, *a.ROA_PROGNOSE_INDICATOREN]),
        ROA_KOLOMMEN,
    ]
    _csv(df, ROA)
    bronnen[ROA] = {"url": "riodata roa.load('ais2030', 'arbeidsmarkt') (ROA AIS 2030)",
                    "filter": "Nederland, opleidingsniveau, de indicatoren van get_roa_benchmark", "rijen": len(df)}  # fmt: skip


def main() -> None:
    MAP.mkdir(parents=True, exist_ok=True)
    bronnen: dict = {}
    tekst: dict = {}
    _duo(bronnen, tekst)
    _mbo_indicatoren(bronnen)
    _inspectie(bronnen)
    _cbs(bronnen)
    _uwv(bronnen)
    _roa(bronnen)
    for info in bronnen.values():
        info["opgehaald"] = date.today().isoformat()
    BRONNEN.write_text(json.dumps(bronnen, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    TEKSTKOLOMMEN.write_text(json.dumps(tekst, indent=1, ensure_ascii=False) + "\n")
    for naam, info in sorted(bronnen.items()):
        print(f"{naam}: {(MAP / naam).stat().st_size} bytes, {info.get('rijen', '-')} rijen")


if __name__ == "__main__":
    main()

"""Retrieval-baseline van search_catalog: vragenset, offline meting, snapshot en release-eis (#359).

Definities en de release-eis staan in README.md. De meting draait één keer per module, zonder
netwerk en zonder instellingsregister; het script draait in een eigen proces, zonder model.
"""

import copy
import json
import re
import socket
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from tests.retrieval_baseline import harnas, rapport
from tools import catalog

ROOT = Path(__file__).resolve().parents[2]
VRAGEN = harnas.laad_vragen()
BASELINE = harnas.laad_baseline()
KRITIEK_FALEND: dict = (BASELINE or {}).get("kritiek_falend", {})

_VERPLICHT = {
    "id": str,
    "sector": str,
    "reeks": str,
    "vraag": str,
    "zoekinput": str,
    "geaccepteerd": list,
    "beantwoordbaar": bool,
    "verboden": list,
    "kritiek": bool,
    "toelichting": str,
}
_OPTIONEEL = {
    "source": ("both", "cbs", "duo", "rio"),
    "geo_niveau": ("gemeente", "provincie", "corop", "landelijk", "landsdeel"),
}
_BINNEN = [v for v in VRAGEN if v["sector"] != rapport.BUITEN_PROFIEL]


def _fouten_in(vraag: dict) -> list[str]:
    fouten = [
        f"{veld} ontbreekt of is geen {soort.__name__}"
        for veld, soort in _VERPLICHT.items()
        if not isinstance(vraag.get(veld), soort)
    ]
    fouten += [f"onbekend veld {veld}" for veld in set(vraag) - set(_VERPLICHT) - set(_OPTIONEEL)]
    fouten += [
        f"{veld}={vraag[veld]!r}"
        for veld, waarden in _OPTIONEEL.items()
        if veld in vraag and vraag[veld] not in waarden
    ]
    if vraag.get("sector") not in (*rapport.SECTOREN, rapport.BUITEN_PROFIEL):
        fouten.append(f"sector={vraag.get('sector')!r}")
    if vraag.get("reeks") not in rapport.REEKSEN:
        fouten.append(f"reeks={vraag.get('reeks')!r}")
    if vraag.get("beantwoordbaar") != bool(vraag.get("geaccepteerd")):
        fouten.append("beantwoordbaar wijkt af van geaccepteerd")
    if set(vraag.get("geaccepteerd") or []) & set(vraag.get("verboden") or []):
        fouten.append("een ID is zowel geaccepteerd als verboden")
    if vraag.get("kritiek") and not vraag.get("verboden"):
        fouten.append("kritiek zonder verboden ID's")
    return fouten


def test_vragenset_heeft_60_tot_100_vragen_met_een_uniek_id():
    assert 60 <= len(VRAGEN) <= 100, len(VRAGEN)
    assert [i for i, n in Counter(v["id"] for v in VRAGEN).items() if n > 1] == []


def test_elke_vraag_heeft_geldige_velden():
    fouten = {v.get("id", "?"): f for v in VRAGEN if (f := _fouten_in(v))}
    assert fouten == {}


def test_elke_sector_heeft_minstens_15_vragen_en_buiten_profiel_hoogstens_8():
    telling = Counter(v["sector"] for v in VRAGEN)
    assert all(telling[sector] >= 15 for sector in rapport.SECTOREN), telling
    assert telling[rapport.BUITEN_PROFIEL] <= 8, telling


def test_minstens_8_onbeantwoordbare_vragen_binnen_het_profiel():
    assert sum(not v["geaccepteerd"] for v in _BINNEN) >= 8


def test_buiten_profiel_is_onbeantwoordbaar_en_kritiek():
    buiten = [
        v["id"] for v in VRAGEN if v["sector"] == rapport.BUITEN_PROFIEL and (v["geaccepteerd"] or not v["kritiek"])
    ]
    assert buiten == []


def test_testreeks_is_minstens_een_kwart_en_minstens_5_per_sector():
    assert sum(v["reeks"] == "test" for v in VRAGEN) >= len(VRAGEN) / 4
    for sector in rapport.SECTOREN:
        vragen = [v for v in VRAGEN if v["sector"] == sector]
        test = [v for v in vragen if v["reeks"] == "test"]
        assert len(test) >= 5 and len(test) >= len(vragen) / 4, f"{sector}: {len(test)} van {len(vragen)} in test"


def test_minstens_10_kritieke_vragen():
    assert sum(v["kritiek"] for v in VRAGEN) >= 10


def test_geaccepteerde_ids_zijn_doorzoekbaar_binnen_het_profiel():
    doorzoekbaar = set(harnas.doorzoekbare_ids())
    fout = {
        v["id"]: sorted(set(v["geaccepteerd"]) - doorzoekbaar) for v in VRAGEN if set(v["geaccepteerd"]) - doorzoekbaar
    }
    assert fout == {}, f"Niet doorzoekbaar binnen het profiel: {fout}"


def test_verboden_ids_bestaan_in_de_volledige_inventaris():
    inventaris = harnas.inventaris_ids()
    fout = {v["id"]: sorted(set(v["verboden"]) - inventaris) for v in VRAGEN if set(v["verboden"]) - inventaris}
    assert fout == {}, f"Niet in _cbs_alles of _rio_duo_alles: {fout}"


_PERSOONSGEGEVENS = {
    "e-mailadres": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "telefoonnummer": re.compile(r"(?:\+31|\b0)[\s-]?\d(?:[\s-]?\d){8}\b"),
    "BSN-achtig getal": re.compile(r"\b\d{9}\b"),
}


def test_de_persoonsgegevenspatronen_vinden_wat_ze_moeten_vinden():
    voorbeelden = {
        "e-mailadres": "mail info@instelling.nl",
        "telefoonnummer": "bel 06-12345678",
        "BSN-achtig getal": "bsn 123456782",
    }
    assert all(_PERSOONSGEGEVENS[naam].search(tekst) for naam, tekst in voorbeelden.items())


def test_vragenset_bevat_geen_persoonsgegevens():
    tekst = harnas.VRAGENSET.read_text(encoding="utf-8")
    gevonden = {naam: hits for naam, patroon in _PERSOONSGEGEVENS.items() if (hits := patroon.findall(tekst))}
    assert gevonden == {}


@pytest.fixture(scope="module")
def gemeten() -> harnas.Meting:
    return harnas.meet(VRAGEN)


def test_netwerkblokkade_houdt_elke_verbinding_tegen():
    origineel = socket.socket.connect
    with harnas.zonder_netwerk() as pogingen:
        with pytest.raises(harnas.NetwerkGeblokkeerd):
            socket.create_connection(("192.0.2.1", 80), timeout=1)
        with socket.socket() as sock, pytest.raises(harnas.NetwerkGeblokkeerd):
            sock.connect(("192.0.2.1", 80))
        with pytest.raises(harnas.NetwerkGeblokkeerd):
            socket.getaddrinfo("example.org", 443)
    assert len(pogingen) == 3
    assert socket.socket.connect is origineel


def test_meting_maakt_geen_netwerkverbinding(gemeten):
    assert gemeten.netwerkpogingen == []


def test_script_laadt_geen_model_en_eindigt_met_0():
    """In een eigen proces: in de testsessie hebben andere tests litellm al geïmporteerd."""
    script = ROOT / "scripts" / "meet_retrieval.py"
    code = (
        "import runpy, sys\n"
        f"main = runpy.run_path({str(script)!r})['main']\n"
        "code = main([])\n"
        "print('LITELLM', 'litellm' in sys.modules, 'EXIT', code)\n"
    )
    uit = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=180, check=False
    )
    assert "LITELLM False EXIT 0" in uit.stdout, uit.stdout[-3000:] + uit.stderr[-3000:]
    assert all(re.search(rf"^{re.escape(naam)}\s", uit.stdout, re.MULTILINE) for naam in rapport.CELLEN), uit.stdout


def test_tekstresultaat_is_een_lege_ranglijst():
    assert harnas.ranking("no_match: Geen resultaten gevonden voor 'x'.", {}) == []
    assert harnas.ranking("Geen datasets gevonden voor 'x' die het niveau 'gemeente' ondersteunen.", {}) == []


def test_melding_in_de_uitvoer_is_geen_treffer():
    uitvoer = json.dumps([{"_cbs_id": "85423NED"}, {"melding": "Query genormaliseerd naar trefwoorden"}])
    assert harnas.ranking(uitvoer, {}) == ["85423NED"]


def test_roa_treffer_krijgt_zijn_id_via_de_unieke_titel():
    with harnas.zonder_instellingsregister():
        uitvoer = catalog.search_catalog("AIS tot 2030 arbeidsmarkt", top_n=15)
    # De zoekuitvoer houdt _roa_id niet (_SEARCH_KEEP_FIELDS); daarom de terugval op de titel.
    roa = next(t for t in json.loads(uitvoer) if t.get("bron") == "AIS tot 2030")
    titels = harnas.unieke_titels(harnas.doorzoekbaar())
    assert harnas.treffer_id(roa, titels) == "ais2030"
    assert "ais2030" in harnas.ranking(uitvoer, titels)


def test_elke_treffer_in_de_meting_heeft_een_id(gemeten):
    onbekend = [u.vraag["id"] for u in gemeten.uitkomsten if harnas.ONBEKEND in u.ranking + u.ranking_vraag]
    assert onbekend == []


_OPNIEUW = f"Meet opnieuw met `{rapport.OPNIEUW_METEN}` en controleer de labels in vragenset.json (README.md)."


def test_catalogus_is_de_gemeten_snapshot():
    assert BASELINE is not None, f"baseline.json ontbreekt. {_OPNIEUW}"
    nu = harnas.snapshot()
    if nu["catalogus_digest"] != BASELINE["catalogus_digest"]:
        weg = sorted(set(BASELINE["doorzoekbaar"]) - set(nu["doorzoekbaar"]))
        erbij = sorted(set(nu["doorzoekbaar"]) - set(BASELINE["doorzoekbaar"]))
        pytest.fail(
            f"De catalogus wijkt af van de gemeten snapshot: digest {nu['catalogus_digest']}, baseline "
            f"{BASELINE['catalogus_digest']} ({BASELINE['gemeten_op']}); weg {weg}, erbij {erbij}. {_OPNIEUW}"
        )


def test_baseline_kent_alleen_kritieke_vragen_als_falend():
    kritiek = {v["id"] for v in VRAGEN if v["kritiek"]}
    assert set(KRITIEK_FALEND) <= kritiek


_KRITIEK = [
    pytest.param(
        v,
        id=v["id"],
        marks=[pytest.mark.xfail(strict=True, reason=f"baseline: {KRITIEK_FALEND[v['id']]}")]
        if v["id"] in KRITIEK_FALEND
        else [],
    )
    for v in VRAGEN
    if v["kritiek"]
]


@pytest.mark.parametrize("vraag", _KRITIEK)
def test_kritieke_vraag_heeft_geen_verboden_dataset_in_de_top_5(vraag, gemeten):
    """Release-eis (README.md): een verboden ID in de top 5 faalt, op ontwikkel en test."""
    verboden = gemeten.uitkomst(vraag["id"]).verboden_top
    gevonden = ", ".join(f"{i} op rang {r}" for i, r in verboden.items())
    assert not verboden, f"{vraag['id']}: verboden dataset in de top 5 voor {vraag['zoekinput']!r}: {gevonden}"


def test_rapport_heeft_een_rij_per_sector_en_reeks(gemeten):
    tekst = rapport.tekst(gemeten, BASELINE, harnas.snapshot())
    ontbreekt = [naam for naam in rapport.CELLEN if not re.search(rf"^{re.escape(naam)}\s", tekst, re.MULTILINE)]
    assert ontbreekt == []


def test_kleine_cel_heet_indicatief(gemeten):
    tekst = rapport.tekst(gemeten, BASELINE, harnas.snapshot())
    for cel in rapport.cellen(gemeten.uitkomsten):
        rij = next(r for r in tekst.splitlines() if r.startswith(f"{cel.naam} "))
        assert rij.endswith("indicatief") == (cel.zoekinput.n < rapport.INDICATIEF_ONDER), rij


def _heeft_detail(tekst: str, vraag_id: str) -> bool:
    return re.search(rf"^  {re.escape(vraag_id)} ", tekst, re.MULTILINE) is not None


def test_details_van_de_testreeks_alleen_op_verzoek(gemeten):
    snapshot = harnas.snapshot()
    zonder = rapport.tekst(gemeten, BASELINE, snapshot)
    met = rapport.tekst(gemeten, BASELINE, snapshot, toon_test=True)
    for v in VRAGEN:
        assert _heeft_detail(zonder, v["id"]) == (v["reeks"] == "ontwikkel"), v["id"]
        assert _heeft_detail(met, v["id"]), v["id"]


def test_rapport_geeft_het_verschil_met_de_baseline(gemeten):
    nu = rapport.baseline(gemeten, harnas.snapshot(), "2026-10-09")
    oud = copy.deepcopy(nu)
    oud["metingen"]["totaal/ontwikkel"]["recall_at_5"] -= 0.1
    rij = next(
        r for r in rapport.tekst(gemeten, oud, harnas.snapshot()).splitlines() if r.startswith("totaal/ontwikkel")
    )
    assert "+0.10" in rij


def test_baseline_heeft_een_meting_per_cel(gemeten):
    nu = rapport.baseline(gemeten, harnas.snapshot(), "2026-10-09")
    assert set(nu["metingen"]) == set(rapport.CELLEN)
    assert BASELINE is not None and set(BASELINE["metingen"]) == set(rapport.CELLEN)


def test_nieuwe_baseline_met_een_extra_falende_kritieke_vraag_is_een_regressie():
    oud = {"kritiek_falend": {"hbo-09": {"p01hoinges": 2}}}
    nieuw = {"kritiek_falend": {"hbo-09": {"p01hoinges": 1}, "wo-11": {"p03hoinschr": 4}}}
    assert rapport.nieuw_falend(oud, nieuw) == ["wo-11"]
    assert rapport.nieuw_falend(oud, {"kritiek_falend": {}}) == []
    assert rapport.nieuw_falend(None, nieuw) == []

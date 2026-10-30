"""Jaar- en diplomaresultaat en nieuwe vsv'ers per mbo-instelling, uit DUO's indicatoren per instelling (#727).

Het bestand wordt hier met openpyxl nagebouwd zoals DUO het publiceert: drie koprijen met samengevoegde cellen
(indicator, schooljaar, Inst./Vgl Grp), een lege vierde rij, opvulspaties, een lege cel en een 0. De waarden van
ROC Midden Nederland (25LH) en de groepswaarden zijn die van de editie 2026.
"""

import io
import json

import httpx
import openpyxl
import pytest

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from scripts import bronping
from tools import fouten, mbo_indicatoren
from tools.schemas import TOOL_GET_MBO_INDICATOREN

JR, DR, VSV = "Jaarresultaat", "Diplomaresultaat", "Percentage nieuwe VSV-ers"
_JAREN = ["2022-2023", "2023-2024", "2024-2025"]
_SLEUTELS = ["Instellingscode", "Naam Instelling", "Soort Instelling", "Straat", "Huisnr", "Postcode", "Plaats",
             "Vgl Groep"]  # fmt: skip
_GROEPSWAARDEN = {
    (JR, "ROC"): [0.690877991916243, 0.708770249234506, 0.717899163108854],
    (DR, "ROC"): [0.704058436638075, 0.719388888536265, 0.72440228349962],
    (VSV, "ROC"): [0.0667601480282179, 0.0632719250278129, 0.0603722239308115],
    (JR, "BER"): [0.696744748707797, 0.711443923630959, 0.713383458646617],
    (DR, "BER"): [0.696746359877764, 0.707002380057622, 0.710967401346179],
    (VSV, "BER"): [0.0493041237113402, 0.0456797647121168, 0.0441854233654877],
}
# (code, naam, soort, groep, waarden per indicator); opvulspaties zoals in de edities 2023 en 2024.
_INSTELLINGEN = [
    ("25LH", "ROC Midden Nederland", "regionaal opleidingencentrum", "ROC", {
        JR: [0.706069880132619, 0.703268713739918, 0.70130783293489],
        DR: [0.712116991643454, 0.71285140562249, 0.705518627299428],
        VSV: [0.0638, 0.064, 0.0614],
    }),
    # Een 0 bij de vsv: in de editie 2026 een fusie-instelling, die in 2025 nog 6,44% had. Betekent: geen cijfer.
    ("25PT", "Talland College", "regionaal opleidingencentrum", "ROC", {
        JR: [0.701032426930348, 0.737044145873321, 0.729236677868459],
        DR: [0.712170517409697, 0.745466534784042, 0.738332739579622],
        VSV: [0.07235, 0, 0],
    }),
    # Eén organisatie, twee BRIN's in verschillende groepen.
    ("25LX", "Curio", "vsg met ROC", "ROC ", {
        JR: [0.68696562554528, 0.712197762540599, 0.709537572254335],
        DR: [0.693264862729607, 0.724927775484936, 0.711175020542317],
        VSV: [0.0766, 0.0652, 0.0594],
    }),
    ("21CY", "Curio", "vsg met beroepscollege", "BER", {
        JR: [0.647855530474041, 0.65989847715736, 0.647058823529412],
        DR: [0.649411764705882, 0.663072776280323, 0.637362637362637],
        VSV: [0.048, 0.055, 0.0556],
    }),
    # Afgekapte naam met opvulspaties en een lege cel.
    ("02PA ", "Mediacollege Amsterdam Ma ", "vsg met beroepscollege ", "BER ", {
        JR: [None, 0.661795407098121, 0.643419572553431],
        DR: [0.61864406779661, 0.657579062159215, 0.644675925925926],
        VSV: [0.0589, 0.0478, ""],
    }),
]  # fmt: skip


def _blad(boek: openpyxl.Workbook, naam: str, indicatoren: list[str], tussenkolom: bool) -> None:
    """Een sheet zoals DUO hem schrijft: `JR en DR` met de jaren aaneen, `VSV` met een lege kolom tussen de jaren."""
    blad = boek.create_sheet(naam)
    for k, kop in enumerate(_SLEUTELS, 1):
        blad.cell(3, k, kop)
    blad.cell(2, 4, "Vestigingsadres")
    blad.merge_cells(start_row=2, start_column=4, end_row=2, end_column=7)
    plekken: dict[tuple[str, int], int] = {}
    kolom = len(_SLEUTELS) + 2
    for indicator in indicatoren:
        begin = kolom
        for j, jaar in enumerate(_JAREN):
            kolom += 1 if j and tussenkolom else 0
            blad.cell(2, kolom, jaar)
            blad.merge_cells(start_row=2, start_column=kolom, end_row=2, end_column=kolom + 1)
            blad.cell(3, kolom, "Inst.")
            blad.cell(3, kolom + 1, "Vgl Grp")
            plekken[(indicator, j)] = kolom
            kolom += 2
        blad.cell(1, begin, indicator)
        blad.merge_cells(start_row=1, start_column=begin, end_row=1, end_column=kolom - 1)
        kolom += 1
    for r, (code, naam_, soort, groep, waarden) in enumerate(_INSTELLINGEN, 5):
        for k, w in enumerate([code, naam_, soort, "Straat", 1, "1234AB", "PLAATS", groep], 1):
            blad.cell(r, k, w)
        blad.cell(r, len(_SLEUTELS) + 1, "")
        for (indicator, j), k in plekken.items():
            blad.cell(r, k, waarden[indicator][j])
            blad.cell(r, k + 1, _GROEPSWAARDEN[(indicator, groep.strip())][j])


def _boek() -> openpyxl.Workbook:
    boek = openpyxl.Workbook()
    boek.remove(boek.active)
    _blad(boek, "JR en DR", [JR, DR], tussenkolom=False)
    _blad(boek, "VSV", [VSV], tussenkolom=True)
    boek.create_sheet("Financieel").cell(3, 1, "Instellingscode")
    return boek


def _bytes(boek: openpyxl.Workbook) -> bytes:
    buffer = io.BytesIO()
    boek.save(buffer)
    return buffer.getvalue()


_XLSX = _bytes(_boek())
_URL = "https://duo.nl/open_onderwijsdata/images/2026-indicatoren-per-instelling.xlsx"
_XLSX_SOORT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _rij(jaar: int, peildatum: str) -> str:
    return (
        f'<tr><td scope="row"><span class="file__title break-all"><a href="/open_onderwijsdata/images/'
        f'{jaar}-indicatoren-per-instelling.xlsx" target="new">Indicatoren {jaar}</a></span> (xlsx 47kb)</td>'
        f"\n<td >{peildatum}</td>\n<td >1 april {jaar}</td></tr>"
    )


_PAGINA = (
    '<table><tbody><tr><td><a href="/open_onderwijsdata/images/2022-indicatoren-per-instelling.xls">2022</a></td>'
    f"<td >1 oktober 2021</td></tr>{_rij(2026, '1 oktober 2025')}{_rij(2025, '1 oktober 2024')}</tbody></table>"
)


def _editie(inhoud: bytes = _XLSX) -> mbo_indicatoren.Editie:
    gelezen, groepswaarden, schooljaren = mbo_indicatoren.lees_xlsx(inhoud)
    return mbo_indicatoren.Editie(2026, _URL, "1 oktober 2025", gelezen, groepswaarden, schooljaren)


def _weigert(boek: openpyxl.Workbook, tekst: str) -> None:
    with pytest.raises(mbo_indicatoren.IndicatorenAfwijkend, match=tekst):
        mbo_indicatoren.lees_xlsx(_bytes(boek))


# --- de koppen ------------------------------------------------------------------------------------------------


def test_de_kolommen_komen_uit_de_koppen_met_doorgevulde_samengevoegde_cellen():
    blad = openpyxl.load_workbook(io.BytesIO(_XLSX))["JR en DR"]
    sleutels, data = mbo_indicatoren.kolommen("JR en DR", mbo_indicatoren._koprijen(blad))

    assert sleutels["Instellingscode"] == 0 and sleutels["Vgl Groep"] == 7
    # Zoals in de echte bestanden: jaarresultaat in de kolommen 9-14, diplomaresultaat in 16-21.
    assert sorted(data) == [9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21]
    assert (data[9].indicator, data[9].schooljaar, data[9].van_groep) == ("jaarresultaat", "2022/23", False)
    assert (data[14].indicator, data[14].schooljaar, data[14].van_groep) == ("jaarresultaat", "2024/25", True)
    assert (data[20].indicator, data[20].schooljaar) == ("diplomaresultaat", "2024/25")


def test_de_vsv_sheet_met_lege_kolommen_tussen_de_jaren():
    blad = openpyxl.load_workbook(io.BytesIO(_XLSX))["VSV"]
    _, data = mbo_indicatoren.kolommen("VSV", mbo_indicatoren._koprijen(blad))
    assert sorted(data) == [9, 10, 12, 13, 15, 16]
    assert {k.indicator for k in data.values()} == {"nieuwe_vsv"}


@pytest.mark.parametrize(("kop", "jaar"), [("2024-2025", "2024/25"), ("2024 - 2025", "2024/25"), ("2024-2026", None),
                                           ("2024", None), ("", None)])  # fmt: skip
def test_het_schooljaar_uit_de_kop(kop, jaar):
    assert mbo_indicatoren.schooljaar(kop) == jaar


def test_een_onbekende_kop_wordt_geweigerd():
    boek = _boek()
    boek["JR en DR"].cell(3, 11, "Mediaan")
    _weigert(boek, "onbekende kop 'Mediaan'")


def test_een_verschoven_kop_wordt_geweigerd():
    boek = _boek()
    blad = boek["VSV"]
    blad.cell(3, 12, "Vgl Grp")  # in de lege kolom tussen twee jaren, dus zonder schooljaar erboven
    blad.cell(3, 11, None)
    _weigert(boek, "staat onder")


def test_een_onbekende_indicator_wordt_geweigerd():
    boek = _boek()
    boek["JR en DR"].cell(1, 10, "Slaagpercentage")
    _weigert(boek, "Slaagpercentage")


def test_een_onbekende_of_ontbrekende_sheet_wordt_geweigerd():
    boek = _boek()
    boek.create_sheet("Personeel")
    _weigert(boek, "onbekende sheet")
    boek = _boek()
    boek.remove(boek["VSV"])
    _weigert(boek, "ontbreken")


def test_zonder_instellingscode_in_de_kop_een_weigering():
    boek = _boek()
    boek["VSV"].cell(3, 1, "Brinnr")  # de kop van de edities 2021-2022
    _weigert(boek, "onbekende kop 'Brinnr'")


# --- de regels in de code -------------------------------------------------------------------------------------


def test_opvulspaties_worden_gestript_en_namen_blijven_zoals_ze_zijn():
    gelezen, _, schooljaren = mbo_indicatoren.lees_xlsx(_XLSX)
    assert set(gelezen) == {"25LH", "25PT", "25LX", "21CY", "02PA"}
    assert gelezen["02PA"].naam == "Mediacollege Amsterdam Ma" and gelezen["02PA"].groep == "BER"
    assert gelezen["25LX"].groep == "ROC"
    assert schooljaren["nieuwe_vsv"] == ("2022/23", "2023/24", "2024/25")


@pytest.mark.parametrize("waarde", [None, "", "  ", 0, 0.0])
def test_een_lege_cel_of_een_exacte_nul_is_geen_cijfer(waarde):
    assert mbo_indicatoren.aandeel(waarde) is None


@pytest.mark.parametrize("waarde", [70.1, 1.2, -0.1, "70,1", True, float("nan")])
def test_een_waarde_buiten_0_en_1_of_geen_getal_wordt_geweigerd(waarde):
    with pytest.raises(mbo_indicatoren.IndicatorenAfwijkend):
        mbo_indicatoren.aandeel(waarde)


def test_een_percentage_in_procenten_in_plaats_van_als_fractie_wordt_geweigerd():
    boek = _boek()
    boek["JR en DR"].cell(5, 14, 70.13)
    _weigert(boek, "niet tussen 0 en 1")


@pytest.mark.parametrize(("code", "groep", "tekst"), [("25-LH", "ROC", "geen unieke BRIN"),
                                                      ("25PT", "ROC", "geen unieke BRIN"),
                                                      ("25LH", "AOC", "onbekende vergelijkingsgroep 'AOC'")])  # fmt: skip
def test_een_ongeldige_brin_of_groep_wordt_geweigerd(code, groep, tekst):
    boek = _boek()
    boek["JR en DR"].cell(5, 1, code)
    boek["JR en DR"].cell(5, 8, groep)
    _weigert(boek, tekst)


def test_swap_alarm_als_de_groepswaarde_binnen_een_groep_verschilt():
    """De eerste parse in de verkenning verwisselde instellings- en groepskolom bij 2023/24."""
    boek = _boek()
    blad = boek["JR en DR"]
    # 25LH, jaarresultaat 2023/24: instelling en groep verwisseld.
    blad.cell(5, 12).value, blad.cell(5, 13).value = blad.cell(5, 13).value, blad.cell(5, 12).value
    _weigert(boek, "verschilt binnen ROC: kolommen verwisseld")


# --- ophalen --------------------------------------------------------------------------------------------------


def _site(**anders: tuple[int, str, bytes | str]) -> httpx.Client:
    paginas = {
        mbo_indicatoren.PAGINA: (200, "text/html;charset=UTF-8", _PAGINA),
        _URL: (200, _XLSX_SOORT, _XLSX),
        **anders,
    }

    def antwoord(verzoek: httpx.Request) -> httpx.Response:
        status, soort, inhoud = paginas.get(str(verzoek.url), (404, "text/html", ""))
        inhoud = inhoud if isinstance(inhoud, bytes) else inhoud.encode()
        return httpx.Response(status, content=inhoud, headers={"content-type": soort})

    return httpx.Client(transport=httpx.MockTransport(antwoord))


def test_de_nieuwste_xlsx_editie_met_haar_peildatum():
    assert mbo_indicatoren.nieuwste_editie(_PAGINA) == (2026, _URL, "1 oktober 2025")


def test_de_code_haalt_de_nieuwste_editie_en_leest_hem():
    gelezen = mbo_indicatoren.haal_editie(_site())
    assert (gelezen.jaar, gelezen.url, gelezen.peildatum) == (2026, _URL, "1 oktober 2025")
    assert len(gelezen.instellingen) == 5


@pytest.mark.parametrize(
    ("soort", "inhoud"),
    [("text/html;charset=UTF-8", "<!DOCTYPE html><html>Pagina niet gevonden</html>"), (_XLSX_SOORT, b"<html>")],
)
def test_een_soft_404_is_een_melding_geen_parsefout(soort, inhoud):
    """Een ontbrekend bestand geeft bij DUO een redirect naar een foutpagina met HTTP 200."""
    with pytest.raises(mbo_indicatoren.IndicatorenOnbereikbaar, match="geen xlsx-bestand"):
        mbo_indicatoren.haal_editie(_site(**{_URL: (200, soort, inhoud)}))


def test_zonder_editie_op_de_pagina_of_bij_een_fout_van_duo_een_melding():
    with pytest.raises(mbo_indicatoren.IndicatorenOnbereikbaar, match="noemt geen xlsx-editie"):
        mbo_indicatoren.haal_editie(_site(**{mbo_indicatoren.PAGINA: (200, "text/html", "<p>leeg</p>")}))
    with pytest.raises(mbo_indicatoren.IndicatorenOnbereikbaar, match="antwoordde niet"):
        mbo_indicatoren.haal_editie(_site(**{mbo_indicatoren.PAGINA: (503, "text/html", "")}))


# --- de tool get_mbo_indicatoren ------------------------------------------------------------------------------

_PROFIELEN = {
    "roc midden nederland": {"naam": "ROC Midden Nederland", "sector": "mbo", "instellingscode": "25LH"},
    "talland college": {"naam": "Talland College", "sector": "mbo", "instellingscode": "25PT"},
    "curio": {"naam": "Curio", "sector": "mbo", "instellingscode": "21CY"},
    "mediacollege amsterdam": {"naam": "Mediacollege Amsterdam", "sector": "mbo", "instellingscode": "02PA"},
    "los mbo": {"naam": "Los MBO", "sector": "mbo", "instellingscode": "99ZZ"},
    "hu": {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"},
}


@pytest.fixture
def tool(monkeypatch):
    gelezen = _editie()
    monkeypatch.setattr(
        mbo_indicatoren.instellingen, "instellingsprofiel", lambda naam: _PROFIELEN.get(naam.strip().lower())
    )
    monkeypatch.setattr(mbo_indicatoren, "editie", lambda: gelezen)
    return lambda naam: json.loads(mbo_indicatoren.get_mbo_indicatoren(naam))


def test_acceptatie_roc_midden_nederland_2024_25(tool):
    """De acceptatiewaarden uit #727: 70,1% en 70,6%, vergelijkingsgroep 71,8% en 72,4%."""
    uit = tool("ROC Midden Nederland")

    assert uit["instelling"] == {"naam": "ROC Midden Nederland", "instellingscode": "25LH"}
    assert uit["vergelijkingsgroep"] == {"code": "ROC", "omschrijving": "roc's (ROC en ROCV)"}
    assert uit["jaarresultaat"][-1] == {
        "schooljaar": "2024/25",
        "instelling": 70.1,
        "vergelijkingsgroep": 71.8,
        "verschil_procentpunt": -1.7,
    }
    assert uit["diplomaresultaat"][-1] == {
        "schooljaar": "2024/25",
        "instelling": 70.6,
        "vergelijkingsgroep": 72.4,
        "verschil_procentpunt": -1.8,
    }
    assert [r["schooljaar"] for r in uit["jaarresultaat"]] == ["2022/23", "2023/24", "2024/25"]
    assert uit["bron"] == {
        "naam": "DUO, Indicatoren per instelling (jaardocument mbo)",
        "url": _URL,
        "editie": 2026,
        "peildatum": "1 oktober 2025",
    }
    assert "licentie" not in uit["bron"]  # nog niet bevestigd door DUO: niets verzinnen


def test_alleen_het_laatste_vsv_jaar_is_voorlopig(tool):
    uit = tool("ROC Midden Nederland")
    assert [r.get("voorlopig", False) for r in uit["nieuwe_vsv"]] == [False, False, True]
    assert uit["nieuwe_vsv"][-1]["instelling"] == 6.1
    assert not any(r.get("voorlopig") for r in uit["jaarresultaat"] + uit["diplomaresultaat"])
    assert "2024/25 is voorlopig" in uit["noot"]
    assert "CBS" in uit["definities"]["nieuwe_vsv"]


def test_een_nul_of_lege_cel_wordt_null_met_uitleg_zonder_verschil(tool):
    talland = tool("Talland College")["nieuwe_vsv"]
    assert talland[0]["instelling"] == 7.2  # 0,07235 rondt half naar boven
    assert talland[1] == {"schooljaar": "2023/24", "instelling": None, "vergelijkingsgroep": 6.3,
                          "uitleg": "geen cijfer"}  # fmt: skip
    media = tool("Mediacollege Amsterdam")
    assert media["jaarresultaat"][0]["instelling"] is None and "verschil_procentpunt" not in media["jaarresultaat"][0]
    assert media["nieuwe_vsv"][-1]["uitleg"] == "geen cijfer"
    assert "geen cijfer" in media["noot"] and "schat er geen" in media["noot"]


def test_twee_brins_onder_een_naam_worden_nooit_samengenomen(tool):
    uit = tool("Curio")
    assert uit["instelling"]["instellingscode"] == "21CY" and uit["vergelijkingsgroep"]["code"] == "BER"
    assert uit["jaarresultaat"][-1]["instelling"] == 64.7  # alleen 21CY, niet gemiddeld met 25LX
    assert "25LX" in uit["noot"] and "tel of middel" in uit["noot"]


@pytest.mark.parametrize(
    ("instelling", "tekst"),
    [
        ("Hogeschool Nergens", "Onbekende instelling"),
        ("HU", "alleen voor het mbo"),
        ("Los MBO", "staat niet in DUO's indicatoren per instelling, editie 2026"),
    ],
)
def test_zonder_cijfers_een_vaste_melding(tool, instelling, tekst):
    uit = mbo_indicatoren.get_mbo_indicatoren(instelling)
    assert tekst in uit and not uit.startswith("{")


def test_een_afwijkend_of_onbereikbaar_bestand_is_een_gecodeerde_fout(tool, monkeypatch):
    def afwijkend():
        raise mbo_indicatoren.IndicatorenAfwijkend("onbekende kop 'Mediaan'")

    monkeypatch.setattr(mbo_indicatoren, "editie", afwijkend)
    uit = mbo_indicatoren.get_mbo_indicatoren("ROC Midden Nederland")
    assert fouten.code(uit) == "bron_fout" and "Mediaan" in uit and "noem geen schatting" in uit

    def onbereikbaar():
        try:
            raise httpx.ConnectTimeout("te laat")
        except httpx.ConnectTimeout as e:
            raise mbo_indicatoren.IndicatorenOnbereikbaar("DUO antwoordde niet") from e

    monkeypatch.setattr(mbo_indicatoren, "editie", onbereikbaar)
    uit = mbo_indicatoren.get_mbo_indicatoren("ROC Midden Nederland")
    assert fouten.code(uit) == "bron_onbereikbaar" and "DUO" in uit


def test_de_tool_staat_in_de_dispatch_en_de_bron_onder_het_antwoord(tool):
    uit, _ = tools.dispatch(TOOL_GET_MBO_INDICATOREN, {"instelling": "ROC Midden Nederland"})
    stap = (TOOL_GET_MBO_INDICATOREN, uit)

    regel = "DUO · Indicatoren per instelling (jaardocument mbo), editie 2026, peildatum 1 oktober 2025"
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: _URL}
    assert TOOL_GET_MBO_INDICATOREN in tools.LABELS


def test_de_bron_ping_leest_de_editie_zoals_de_chat():
    ping = next(p for p in bronping.PINGS if p.id == "duo-indicatoren")
    assert ping.bron == "duo"
    assert ping.bewijs({"editie": 2026, "instellingen": 54}) is None
    assert "minstens" in str(ping.bewijs({"editie": 2026, "instellingen": 3}))

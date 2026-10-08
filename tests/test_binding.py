"""Staat een getal bij het jaar en de instelling van zijn eigen rij? (#197)

Live-audit 8, lokale reproductie: HU p01 VT 2024/25 = 27.135 en 2025/26 = 26.370.
De zin "2025/26 = 27.135" kwam door getal- en periodecontrole, omdat beide jaren
en beide getallen in dezelfde selectie stonden.
"""

import json

import pandas as pd
import pytest

from agent.binding import verkeerd_gebonden
from tools import store
from tools.store import KeyMeta

_KEY = "duo:p01hoinges:3:sel"


@pytest.fixture(autouse=True)
def _selectie():
    store.clear()
    df = pd.DataFrame(
        {
            "STUDIEJAAR": [2024, 2025, 2024, 2025],
            "INSTELLINGSCODE_ACTUEEL": ["25DW", "25DW", "30TX", "30TX"],
            "INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht"] * 2 + ["Aeres Hogeschool"] * 2,
            "AANTAL": [27135, 26370, 2991, 2880],
        }
    )
    store.put(
        _KEY,
        df,
        KeyMeta(
            bron="duo",
            dataset="p01hoinges",
            periodekolom="STUDIEJAAR",
            instellingskolom="INSTELLINGSCODE_ACTUEEL",
            afgeleid_van="duo:p01hoinges:3",
        ),
    )
    yield
    store.clear()


def _beurt() -> list[str]:
    return [json.dumps({"data_key": _KEY})]


def test_getal_van_een_ander_geselecteerd_jaar():
    [probleem] = verkeerd_gebonden("In 2025/26 waren het 27.135 voltijdstudenten.", _beurt())
    assert "27.135" in probleem and "2024/25" in probleem and "2025/26" in probleem


def test_getal_bij_zijn_eigen_jaar_is_goed():
    assert verkeerd_gebonden("In 2025/26 waren het 26.370 voltijdstudenten.", _beurt()) == []


def test_verwisselde_rij_in_een_markdowntabel():
    tabel = "| Schooljaar | Aantal |\n|---|---|\n| 2024/25 | 27.135 |\n| 2025/26 | 27.135 |"
    [probleem] = verkeerd_gebonden(tabel, _beurt())
    assert "2025/26" in probleem


def test_getal_van_een_andere_geselecteerde_instelling():
    [probleem] = verkeerd_gebonden("Hogeschool Utrecht telde 2.880 voltijdstudenten.", _beurt())
    assert "Aeres Hogeschool" in probleem


def test_getal_zonder_jaar_of_instelling_in_de_zin_is_ongewijzigd():
    assert verkeerd_gebonden("Het waren er 27.135.", _beurt()) == []


def test_zin_met_twee_jaren_is_niet_eenduidig():
    tekst = "Van 27.135 in 2024/25 naar 26.370 in 2025/26."
    assert verkeerd_gebonden(tekst, _beurt()) == []


def test_vergelijking_met_een_eerder_jaar_noemt_maar_een_jaar():
    """#379: 'vijf jaar eerder (2020/'21) … van 518.940 naar 475.460' werd geweigerd, terwijl het klopte."""
    tekst = "Ten opzichte van een jaar eerder (2024/'25) is het aantal gedaald van 27.135 naar 26.370."
    assert verkeerd_gebonden(tekst, _beurt()) == []


@pytest.mark.parametrize(
    "tekst",
    [
        "Hogeschool Utrecht komt uit van 27.135 in 2024/25 en komt uit op 26.370.",
        "Hogeschool Utrecht begon in 2024/25 met 27.135 en eindigde met 26.370.",
        "Het verschil tussen 2024/25 (27.135) en het jaar erna (26.370) is klein.",
    ],
)
def test_ch01_vergelijking_zonder_van_naar_noemt_maar_een_jaar(tekst):
    """N22: 'komt uit van … en komt uit op …' had geen cue; 26.370 werd aan 2024/25 gehangen en ingetrokken."""
    assert verkeerd_gebonden(tekst, _beurt()) == []


def test_vergelijking_zonder_getal_bij_het_genoemde_jaar_blijft_verkeerd():
    [probleem] = verkeerd_gebonden("In 2025/26 waren het 27.135 studenten, een stijging.", _beurt())
    assert "27.135" in probleem


def test_vergelijking_bindt_nog_wel_aan_de_instelling():
    tekst = "Hogeschool Utrecht ging van 27.135 in 2024/25 naar 2.880."
    [probleem] = verkeerd_gebonden(tekst, _beurt())
    assert "2.880" in probleem and "Aeres Hogeschool" in probleem


def test_getal_dat_niet_in_de_rijen_staat_is_niet_aan_deze_controle():
    # Een som of KPI: de getalcontrole beslist daarover, niet deze.
    assert verkeerd_gebonden("In 2025/26 samen 29.250.", _beurt()) == []


def test_cbs_label_zonder_periodecode():
    # Sinds #194 kan een selectie Perioden_label houden zonder Perioden.
    store.put(
        "cbs:85423NED:x",
        pd.DataFrame(
            {
                "Perioden_label": ["2024/'25", "2025/'26*"],
                "TotaalIngeschrevenen_1": [378490, 367960],
            }
        ),
        KeyMeta(bron="cbs", dataset="85423NED", periodekolom="Perioden", afgeleid_van="cbs:85423NED"),
    )
    [probleem] = verkeerd_gebonden("In 2025/26 waren het 378.490.", [json.dumps({"data_key": "cbs:85423NED:x"})])
    assert "2024/25" in probleem


def test_gecombineerde_binding_die_twee_losse_controles_passeert():
    # 2024/25 en Aeres staan elk in een rij met 2.880, maar niet in dezelfde rij (die is 2025/26).
    [probleem] = verkeerd_gebonden("Aeres Hogeschool telde in 2024/25 in totaal 2.880 voltijdstudenten.", _beurt())
    assert "2.880" in probleem and "2025/26" in probleem


def test_gecombineerde_binding_in_dezelfde_rij_is_goed():
    assert verkeerd_gebonden("Aeres Hogeschool telde in 2025/26 in totaal 2.880 voltijdstudenten.", _beurt()) == []


def test_vergelijking_met_twee_jaren_moet_bij_een_van_beide_passen():
    # 2.880 hoort bij 2025/26 en blijft dus goed in een zin over 2024/25 en 2025/26.
    assert verkeerd_gebonden("Aeres: 2.991 in 2024/25 en 2.880 in 2025/26.", _beurt()) == []


def test_vergelijking_met_twee_jaren_en_een_getal_van_een_ander_jaar():
    store.put(
        "duo:p01hoinges:3:drie",
        pd.DataFrame(
            {
                "STUDIEJAAR": [2023, 2024, 2025],
                "AANTAL": [11111, 27135, 26370],
            }
        ),
        KeyMeta(bron="duo", dataset="p01hoinges", periodekolom="STUDIEJAAR", afgeleid_van="duo:p01hoinges:3"),
    )
    [probleem] = verkeerd_gebonden(
        "Van 27.135 in 2024/25 naar 11.111 in 2025/26.", [json.dumps({"data_key": "duo:p01hoinges:3:drie"})]
    )
    assert "11.111" in probleem and "2023/24" in probleem


def _tekstselectie(key: str, df: pd.DataFrame, **meta) -> list[str]:
    store.put(key, df, KeyMeta(bron=meta.pop("bron", "duo"), dataset="x", afgeleid_van=key, **meta))
    return [json.dumps({"data_key": key})]


@pytest.mark.parametrize(
    ("df", "meta"),
    [
        # mbo_opleidingsaanbod_cohorten: alleen tekstkolommen (testaudit L1).
        (
            pd.DataFrame({"OPLEIDINGSVORM": ["BOL", "BBL"], "STUDIEJAAR": ["2024", "2025"]}),
            {"periodekolom": "STUDIEJAAR"},
        ),
        # RIO: tekst, zonder periode- of instellingskolom.
        (pd.DataFrame({"naam": ["Hogeschool Utrecht"], "kenmerk": ["hbo"]}), {"bron": "rio"}),
        # Getallen als string.
        (pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL": ["22410"]}).astype(str), {"periodekolom": "STUDIEJAAR"}),
        # Leeg.
        (pd.DataFrame({"STUDIEJAAR": pd.Series([], dtype=str)}), {"periodekolom": "STUDIEJAAR"}),
    ],
)
def test_selectie_zonder_numerieke_kolom_crasht_niet(df, meta):
    """#392: zip(strict=True) gaf 'argument 3 is shorter' op een selectie zonder getallen."""
    beurt = _tekstselectie("duo:tekst:1:sel", df, **meta)
    assert verkeerd_gebonden("In 2024/25 waren het 22.410 studenten bij Hogeschool Utrecht.", beurt) == []


def test_tekstselectie_naast_getallen_houdt_de_controle():
    """Een tekstselectie in dezelfde beurt zet de controle op de numerieke selectie niet uit."""
    beurt = _beurt() + _tekstselectie("duo:tekst:1:sel", pd.DataFrame({"OPLEIDINGSVORM": ["BOL"]}))
    [probleem] = verkeerd_gebonden("In 2025/26 waren het 27.135 voltijdstudenten.", beurt)
    assert "27.135" in probleem


# ── Afgeleide waarden (#409) ─────────────────────────────────────────────────

_CH01 = "cbs:85423NED:ch01"


def _ch01() -> list[str]:
    """CH-01: ingeschrevenen per jaar, met een tweede kolom waarin 3.200 toevallig twee keer staat."""
    store.put(
        _CH01,
        pd.DataFrame(
            {
                "Perioden": ["2020SJ00", "2021SJ00", "2022SJ00", "2023SJ00", "2024SJ00"],
                "TotaalIngeschrevenen_1": [518940, 501100, 489020, 478660, 475460],
                "Promovendi_2": [3150, 3200, 3200, 3240, 3260],
            }
        ),
        KeyMeta(bron="cbs", dataset="85423NED", periodekolom="Perioden", afgeleid_van="cbs:85423NED"),
    )
    return [json.dumps({"data_key": _CH01})]


def test_ch01_verschil_tussen_de_genoemde_jaren_is_geen_verkeerde_binding():
    """Run 46: 478.660 - 475.460 = 3.200 werd ingetrokken omdat 3.200 ook een cel van 2021/22 en 2022/23 is."""
    tekst = (
        "Van 2023/'24 naar 2024/'25 daalde het aantal ingeschrevenen met 3.200, van 478.660 naar 475.460.\n"
        "| Schooljaar | Ingeschrevenen |\n|---|---|\n| 2023/'24 | 478.660 |\n| 2024/'25 | 475.460 |"
    )
    assert verkeerd_gebonden(tekst, _ch01()) == []


def test_verschil_tussen_andere_jaren_blijft_verkeerd():
    # 501.100 − 489.020 = 12.080 is 2021/22 → 2022/23, niet de genoemde jaren; 3.200 is daar geen verschil.
    store.put(
        "cbs:85423NED:verschil",
        pd.DataFrame(
            {
                "Perioden": ["2021SJ00", "2022SJ00", "2023SJ00", "2024SJ00"],
                "TotaalIngeschrevenen_1": [501100, 489020, 478660, 475460],
                "Verschil_2": [None, 12080, 10360, 3200],
            }
        ),
        KeyMeta(bron="cbs", dataset="85423NED", periodekolom="Perioden", afgeleid_van="cbs:85423NED"),
    )
    tekst = "Van 2023/'24 naar 2024/'25 daalde het aantal met 12.080."
    [probleem] = verkeerd_gebonden(tekst, [json.dumps({"data_key": "cbs:85423NED:verschil"})])
    assert "12.080" in probleem and probleem.hard


def test_kpi_met_periode_is_bron_voor_zijn_eigen_jaren():
    """Een compute_kpi-waarde over de genoemde jaren bindt aan die KPI, niet aan een toevallig gelijke cel."""
    kpi = json.dumps({"value": "-3.200", "periode": {"van": "2023/24", "tot": "2024/25"}, "bron": {"metric": "delta"}})
    assert verkeerd_gebonden("Tussen 2023/'24 en 2024/'25 nam het aantal af met 3.200.", [*_ch01(), kpi]) == []


def test_afgeleid_getal_naast_een_volledige_vergelijking_is_twijfel_en_zacht():
    """Beide jaren hebben hun eigen getal; het derde getal is vermoedelijk afgeleid (som, afgerond verschil)."""
    tekst = "Van 2023/'24 naar 2024/'25: van 478.660 naar 475.460, bijna 3.150 minder."
    [probleem] = verkeerd_gebonden(tekst, _ch01())
    assert "3.150" in probleem and not probleem.hard


def test_verkeerde_binding_is_hard():
    [probleem] = verkeerd_gebonden("In 2025/26 waren het 27.135 voltijdstudenten.", _beurt())
    assert probleem.hard

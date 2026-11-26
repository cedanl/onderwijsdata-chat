"""Chat en dashboard kiezen per instelling en jaar hetzelfde DUO-bestand (#1238, besluit #1214).

Tot #1238 nam de chat (`get_maat`) per sector het opleidingsvorm-bestand over alle jaren en voegde het dashboard de
twee geslacht-bestanden samen (resource 0 en 1): voor dezelfde instelling en hetzelfde jaar twee getallen. Hier drie
nepbestanden van p02ho1ejrs (hbo) waarin het leidende bestand van de groep (opleidingsvorm, index 3) in geen enkel jaar
het minst onderdrukte is, en per jaar een ander bestand wint:

- 2023: het geslacht-bestand (0) heeft één -1, de andere twee elk twee: 0 wint, 502.
- 2024: opleidingsvorm (3) en niveau opleiding (2) hebben geen -1, niveau telt meer: 2 wint, 612.
- 2025: alle drie zonder -1 en met hetzelfde totaal: het eerste van de groep (3), 700.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

import data.dashboard as dashboard
from tools import duo, store
from tools.maten import get_maat

_HU = {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"}
_KOLOM = "AANTAL_EERSTEJAARS_INGESCHREVENEN"
_VERWACHT = {2023: 502, 2024: 612, 2025: 700}


def _bestand(uitsplitsing: str, rijen: list[tuple]) -> pd.DataFrame:
    kolommen = ["STUDIEJAAR", "INSTELLINGSCODE_ACTUEEL", "INSTELLINGSNAAM_ACTUEEL", "ONDERDEEL", uitsplitsing, _KOLOM]
    return pd.DataFrame(rijen, columns=kolommen)


def _hu(jaar: int, waarde: str, aantal: int) -> tuple:
    return (jaar, "25DW", "Hogeschool Utrecht", "ECONOMIE", waarde, aantal)


def _ander(uitsplitsing_waarde: str) -> tuple:
    return (2024, "28DN", "Hogeschool van Amsterdam", "ECONOMIE", uitsplitsing_waarde, 40)


def _uu(uitsplitsing_waarde: str) -> tuple:
    return (2024, "21PD", "Universiteit Utrecht", "ECONOMIE", uitsplitsing_waarde, 900)


_BESTANDEN = {
    # hbo, inclusief geslacht
    0: _bestand(
        "GESLACHT",
        [
            _hu(2023, "MAN", 250),
            _hu(2023, "VROUW", 252),
            _hu(2023, "ONBEKEND", -1),
            _hu(2024, "MAN", 300),
            _hu(2024, "VROUW", -1),
            _hu(2024, "ONBEKEND", -1),
            _hu(2025, "MAN", 350),
            _hu(2025, "VROUW", 350),
            _ander("MAN"),
        ],
    ),
    # wo, inclusief geslacht
    1: _bestand("GESLACHT", [_uu("MAN")]),
    # hbo, niveau opleiding
    2: _bestand(
        "OPLEIDINGSCODE_ACTUEEL",
        [
            _hu(2023, "30001", 300),
            _hu(2023, "30002", 200),
            _hu(2023, "30003", -1),
            _hu(2023, "30004", -1),
            _hu(2024, "30001", 400),
            _hu(2024, "30002", 212),
            _hu(2025, "30001", 700),
            _ander("30001"),
        ],
    ),
    # hbo, inclusief opleidingsvorm: het leidende bestand van de groep
    3: _bestand(
        "OPLEIDINGSVORM",
        [
            _hu(2023, "VT", 500),
            _hu(2023, "DT", -1),
            _hu(2023, "DU", -1),
            _hu(2024, "VT", 600),
            _hu(2024, "DT", 10),
            _hu(2025, "VT", 700),
            _ander("VT"),
        ],
    ),
    # wo, inclusief opleidingsvorm en niveau opleiding
    4: _bestand("OPLEIDINGSVORM", [_uu("VT")]),
    5: _bestand("OPLEIDINGSCODE_ACTUEEL", [_uu("60001")]),
}


@pytest.fixture
def bronnen():
    def laad(dataset_id: str, resource: int = 0, **_) -> pd.DataFrame:
        assert dataset_id == "p02ho1ejrs", dataset_id
        return _BESTANDEN[resource].copy()

    for functie in vars(dashboard).values():
        if hasattr(functie, "cache_clear"):
            functie.cache_clear()
    with (
        patch("onderwijsbronnen.duo.load", side_effect=laad),
        patch("tools.maten.instellingen.instellingsprofiel", return_value=_HU),
    ):
        yield
    for functie in vars(dashboard).values():
        if hasattr(functie, "cache_clear"):
            functie.cache_clear()


def _chat() -> dict:
    uit = json.loads(get_maat("eerstejaars_ho", "Hogeschool Utrecht"))
    assert "data_key" in uit, uit
    return uit


def _dashboard() -> tuple[dict[int, int], dict[int, int]]:
    df = dashboard._load_ho_dataset("p02ho1ejrs")
    return dashboard._reeks(df[df["INSTELLINGSCODE_ACTUEEL"] == "25DW"], "STUDIEJAAR", _KOLOM)


@pytest.mark.usefixtures("bronnen")
def test_chat_en_dashboard_geven_per_jaar_hetzelfde_getal_uit_het_minst_onderdrukte_bestand():
    chat = {r["STUDIEJAAR"]: r[_KOLOM] for r in _chat()["rijen"]}
    reeks, _ = _dashboard()
    assert chat == _VERWACHT
    assert reeks == _VERWACHT


@pytest.mark.usefixtures("bronnen")
def test_chat_en_dashboard_noemen_dezelfde_ondergrens():
    # 2023 komt uit het geslacht-bestand met één -1: in beide een ondergrens van één onderdrukte cel, de andere jaren niet.
    uit = _chat()
    key = uit["data_key"]
    jaren = [r["STUDIEJAAR"] for r in uit["rijen"]]
    chat = {jaar: duo.onderdrukt_in_groep(key, rij, _KOLOM) for rij, jaar in enumerate(jaren)}
    _, leeg = _dashboard()
    assert chat == {2023: 1, 2024: 0, 2025: 0}
    assert leeg == {2023: 1}
    assert any("-1" in regel for regel in uit["databewerking"])


@pytest.mark.usefixtures("bronnen")
def test_chat_noemt_het_bestand_per_jaar():
    uit = _chat()
    per_jaar = uit["bestandskeuze"]["per_schooljaar"]
    assert "inclusief geslacht" in per_jaar["2023/24"]
    assert "niveau opleiding" in per_jaar["2024/25"]
    assert "inclusief opleidingsvorm" in per_jaar["2025/26"]
    known = store.meta(key := uit["data_key"])
    assert known is not None and known.telregels, key
    assert any("2023/24" in regel and "geslacht" in regel for regel in known.telregels)


@pytest.mark.usefixtures("bronnen")
def test_het_dashboard_meldt_de_gekozen_bestanden_aan_het_bronblok():
    from core import brongebruik

    with brongebruik.verzamel() as gebruikt:
        dashboard._load_ho_dataset("p02ho1ejrs")
    # 25DW kiest 0, 2 en 3; de wo-instelling 21PD heeft alleen 2024 en kiest bij gelijke stand het eerste wo-bestand (4).
    assert sorted(m["resource"] for m in gebruikt) == [0, 2, 3, 4]


@pytest.mark.usefixtures("bronnen")
def test_de_snippet_maakt_dezelfde_keuze_per_jaar():
    import contextlib
    import io

    from tools import snippet

    script = snippet.generate("get_maat", {"maat": "eerstejaars_ho", "instelling": "Hogeschool Utrecht"})
    assert script is not None and "Bestandskeuze (#1238)" in script
    namespace: dict = {}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(script, "<snippet>", "exec"), namespace)  # het script van de app zelf, op nepdata
    df = namespace["df"]
    assert {int(j): int(n) for j, n in zip(df["STUDIEJAAR"], df[_KOLOM], strict=True)} == _VERWACHT

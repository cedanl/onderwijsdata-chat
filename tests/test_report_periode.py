"""Een rapportgrafiek toont de periode die het rapport noemt (#385)."""

import json

import pandas as pd
import plotly.io as pio

from agent.report import _parse_spec_from_response
from agent.report_periode import bijgesneden
from tools import store
from tools.plot import create_plot


def _figuur(rijen: list[dict], x: str = "STUDIEJAAR", color_by: str | None = None) -> str:
    store.put("test:385", pd.DataFrame(rijen))
    _, fig = create_plot(chart_type="line", x=x, y="AANTAL", title="Aantal", color_by=color_by, data_key="test:385")
    return pio.to_json(fig)


def _x(figure_json: str) -> list:
    return [x for trace in json.loads(figure_json)["data"] for x in trace["x"]]


ELF_JAAR = [{"STUDIEJAAR": j, "AANTAL": 1000 + j} for j in range(2015, 2026)]


def test_tijdas_wordt_bijgesneden_tot_het_genoemde_bereik():
    fig = bijgesneden(_figuur(ELF_JAAR), (2020, 2024))

    assert _x(fig) == [2020, 2021, 2022, 2023, 2024]
    trace = json.loads(fig)["data"][0]
    assert trace["y"] == [3020, 3021, 3022, 3023, 3024]
    assert trace["text"] == ["3.020", "3.021", "3.022", "3.023", "3.024"]


def test_exportrijen_volgen_de_grafiek():
    meta = json.loads(bijgesneden(_figuur(ELF_JAAR), (2020, 2024)))["layout"]["meta"]

    assert [r["STUDIEJAAR"] for r in meta["data"]] == [2020, 2021, 2022, 2023, 2024]


def test_schooljaarlabels_en_meerdere_reeksen():
    rijen = [{"JAAR": f"{j}/{j + 1}", "AANTAL": j, "VORM": vorm} for j in range(2015, 2026) for vorm in ("BOL", "BBL")]
    fig = bijgesneden(_figuur(rijen, x="JAAR", color_by="VORM"), (2023, 2025))

    for trace in json.loads(fig)["data"]:
        assert trace["x"] == ["2023/2024", "2024/2025", "2025/2026"]


def test_geen_tijdas_blijft_ongemoeid():
    rijen = [{"INSTELLING": n, "AANTAL": i} for i, n in enumerate(["HAN", "TU Delft", "UvA"])]
    fig = _figuur(rijen, x="INSTELLING")

    assert bijgesneden(fig, (2020, 2024)) == fig


def test_bereik_buiten_de_data_laat_de_grafiek_staan():
    fig = _figuur(ELF_JAAR)

    assert bijgesneden(fig, (2030, 2034)) == fig


def test_onleesbare_figuur_blijft_ongemoeid():
    assert bijgesneden("fig1", (2020, 2024)) == "fig1"


def test_rapport_snijdt_de_grafiek_bij_tot_de_periode_in_de_grafiektitel():
    spec = _parse_spec_from_response(
        json.dumps(
            {
                "onderzoeksvraag": "Hoeveel mbo-studenten de laatste vijf jaar?",
                "visualisaties": [{"titel": "Aantal mbo-studenten 2020/21-2024/25"}],
                "conclusie": "In de vijf voorgaande schooljaren ...",
            }
        ),
        figures_json=[_figuur(ELF_JAAR)],
        context={"topic": "Hoeveel mbo-studenten de laatste vijf jaar?"},
    )

    assert _x(spec.visualisaties[0]["figure_json"]) == [2020, 2021, 2022, 2023, 2024]


def test_rapport_snijdt_de_grafiek_bij_tot_de_periode_in_de_vraag():
    """De rapporttitel is de vraag van de gebruiker (#416); noemt die een periode, dan geldt die."""
    spec = _parse_spec_from_response(
        json.dumps({"visualisaties": [{"titel": "Studenten per schooljaar"}], "conclusie": "..."}),
        figures_json=[_figuur(ELF_JAAR)],
        context={"topic": "Hoeveel mbo-studenten van 2020/21 tot en met 2024/25?"},
    )

    assert _x(spec.visualisaties[0]["figure_json"]) == [2020, 2021, 2022, 2023, 2024]


def test_een_periode_in_de_titel_van_het_model_telt_niet():
    """Het model schrijft geen titel meer; schrijft het er toch een, dan snijdt die niets bij (#416)."""
    spec = _parse_spec_from_response(
        json.dumps({"title": "Aantal mbo-studenten 2020/21-2024/25", "visualisaties": [{"titel": "Per jaar"}]}),
        figures_json=[_figuur(ELF_JAAR)],
        context={"topic": "Hoeveel mbo-studenten?"},
    )

    assert len(_x(spec.visualisaties[0]["figure_json"])) == 11


def test_de_titel_van_de_visualisatie_gaat_voor():
    spec = _parse_spec_from_response(
        json.dumps(
            {
                "title": "Aantal mbo-studenten 2020/21-2024/25",
                "visualisaties": [{"titel": "Lange reeks 2015/16 tot 2025/26"}],
            }
        ),
        figures_json=[_figuur(ELF_JAAR)],
        context={"topic": "V"},
    )

    assert len(_x(spec.visualisaties[0]["figure_json"])) == 11


def test_zonder_genoemde_periode_blijft_de_reeks_heel():
    spec = _parse_spec_from_response(
        json.dumps({"title": "Aantal mbo-studenten", "visualisaties": [{"titel": "Per jaar"}]}),
        figures_json=[_figuur(ELF_JAAR)],
        context={"topic": "Hoeveel mbo-studenten?"},
    )

    assert len(_x(spec.visualisaties[0]["figure_json"])) == 11

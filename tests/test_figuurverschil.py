"""figuur_verschillen: gewijzigde waarden tussen twee reeksen Plotly-figuren (#346)."""

import json

from agent.figuurverschil import MAX_MELDINGEN, figuur_verschillen


def _figuur(y: list, titel: str = "Instroom", naam: str | None = None) -> str:
    trace: dict = {"type": "bar", "x": ["2023", "2024"], "y": y}
    if naam:
        trace["name"] = naam
    return json.dumps({"data": [trace], "layout": {"title": {"text": titel}}})


def test_identieke_figuren_geven_geen_meldingen():
    fig = _figuur([475460, 478660])
    assert figuur_verschillen([fig], [fig]) == []


def test_gewijzigde_waarde_noemt_oud_en_nieuw_in_nederlandse_notatie():
    [melding] = figuur_verschillen([_figuur([475460, 475460])], [_figuur([475460, 478660])])
    assert "'Instroom'" in melding
    assert "2024" in melding
    assert "475.460 → 478.660" in melding


def test_reeksnaam_komt_in_de_melding():
    [melding] = figuur_verschillen([_figuur([1, 2], naam="hbo")], [_figuur([1, 3], naam="hbo")])
    assert "reeks 'hbo'" in melding


def test_nieuwe_en_verdwenen_categorie():
    oud = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {}})
    nieuw = json.dumps({"data": [{"type": "bar", "x": ["2024"], "y": [1]}], "layout": {}})
    meldingen = figuur_verschillen([oud], [nieuw])
    assert any("nieuw in de data: 2024" in m for m in meldingen)
    assert any("niet meer in de data: 2023" in m for m in meldingen)


def test_taartgrafiek_vergelijkt_labels_en_values():
    oud = json.dumps({"data": [{"type": "pie", "labels": ["hbo", "wo"], "values": [10, 20]}], "layout": {}})
    nieuw = json.dumps({"data": [{"type": "pie", "labels": ["hbo", "wo"], "values": [10, 25]}], "layout": {}})
    [melding] = figuur_verschillen([oud], [nieuw])
    assert "wo" in melding
    assert "20 → 25" in melding


def test_ander_aantal_grafieken_wordt_gemeld():
    fig = _figuur([1, 2])
    meldingen = figuur_verschillen([fig], [fig, _figuur([3, 4], titel="Extra")])
    assert any("aantal grafieken veranderde van 1 naar 2" in m for m in meldingen)


def test_ander_aantal_reeksen_wordt_gemeld():
    oud = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {}})
    nieuw = json.dumps(
        {"data": [{"type": "bar", "x": ["2023"], "y": [1]}, {"type": "bar", "x": ["2023"], "y": [2]}], "layout": {}}
    )
    [melding] = figuur_verschillen([oud], [nieuw])
    assert "aantal reeksen veranderde van 1 naar 2" in melding


def test_onleesbare_figuur_geeft_een_generieke_melding():
    meldingen = figuur_verschillen(["geen json"], ["ook geen json"])
    assert meldingen == ["Grafiek 1 is gewijzigd."]


def test_meldingen_blijven_begrensd():
    jaren = [str(j) for j in range(2000, 2020)]
    oud = json.dumps({"data": [{"type": "bar", "x": jaren, "y": list(range(20))}], "layout": {}})
    nieuw = json.dumps({"data": [{"type": "bar", "x": jaren, "y": list(range(1, 21))}], "layout": {}})
    meldingen = figuur_verschillen([oud], [nieuw])
    assert len(meldingen) == MAX_MELDINGEN + 1
    assert "andere wijzigingen" in meldingen[-1]


def test_alleen_opmaak_gewijzigd_geeft_geen_datamelding():
    oud = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {"title": {"text": "A"}}})
    nieuw = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {"title": {"text": "B"}}})
    assert figuur_verschillen([oud], [nieuw]) == []


def test_float_ruis_geeft_geen_x_naar_x_melding():
    # nl_getal toont beide als "0,3": een melding "0,3 → 0,3" zou de gebruiker misleiden.
    assert figuur_verschillen([_figuur([0.3, 1])], [_figuur([0.30000000000000004, 1])]) == []


def test_verschil_onder_de_getoonde_precisie_wordt_bewust_niet_gemeld():
    # 0,123 en 0,124 tonen beide als "0,1": gelijkheid volgt wat de gebruiker ziet (één decimaal).
    assert figuur_verschillen([_figuur([0.123, 1])], [_figuur([0.124, 1])]) == []


def test_verschil_op_de_getoonde_precisie_wordt_wel_gemeld():
    [melding] = figuur_verschillen([_figuur([0.14, 1])], [_figuur([0.16, 1])])
    assert "0,1 → 0,2" in melding


def test_geheel_getal_en_bijna_gelijke_float_zijn_gelijk():
    assert figuur_verschillen([_figuur([2, 1])], [_figuur([2.04, 1])]) == []


def test_min_nul_en_nul_zijn_gelijk():
    assert figuur_verschillen([_figuur([-0.04, 1])], [_figuur([0, 1])]) == []

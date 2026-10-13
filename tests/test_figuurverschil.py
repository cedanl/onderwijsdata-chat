"""figuur_verschillen: gewijzigde waarden tussen bewaarde en verse Plotly-figuren (#346, #523).

De figuren zijn gekoppeld op recept-id (een sleutel per figuurrecept), niet op positie.
"""

import json

from agent.figuurverschil import MAX_MELDINGEN, figuur_verschillen


def _figuur(y: list, titel: str = "Instroom", naam: str | None = None, x: list | None = None) -> str:
    trace: dict = {"type": "bar", "x": x or ["2023", "2024"], "y": y}
    if naam:
        trace["name"] = naam
    return json.dumps({"data": [trace], "layout": {"title": {"text": titel}}})


def _heatmap(z: list, titel: str | None = "Instroom per sector", labels: bool = True) -> str:
    trace: dict = {"type": "heatmap", "z": z}
    if labels:
        trace["x"] = ["2023", "2024"]
        trace["y"] = ["hbo", "wo"]
    layout = {"title": {"text": titel}} if titel else {}
    return json.dumps({"data": [trace], "layout": layout})


def _verschil(oud: str, nieuw: str) -> list[str]:
    """Eén figuur, aan beide kanten onder hetzelfde recept-id."""
    return figuur_verschillen({"recept": oud}, {"recept": nieuw})


def test_identieke_figuren_geven_geen_meldingen():
    fig = _figuur([475460, 478660])
    assert _verschil(fig, fig) == []


def test_gewijzigde_waarde_noemt_oud_en_nieuw_in_nederlandse_notatie():
    [melding] = _verschil(_figuur([475460, 475460]), _figuur([475460, 478660]))
    assert "'Instroom'" in melding
    assert "2024" in melding
    assert "475.460 → 478.660" in melding


def test_reeksnaam_komt_in_de_melding():
    [melding] = _verschil(_figuur([1, 2], naam="hbo"), _figuur([1, 3], naam="hbo"))
    assert "reeks 'hbo'" in melding


def test_nieuwe_en_verdwenen_categorie():
    oud = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {}})
    nieuw = json.dumps({"data": [{"type": "bar", "x": ["2024"], "y": [1]}], "layout": {}})
    meldingen = _verschil(oud, nieuw)
    assert any("nieuw in de data: 2024" in m for m in meldingen)
    assert any("niet meer in de data: 2023" in m for m in meldingen)


def test_taartgrafiek_vergelijkt_labels_en_values():
    oud = json.dumps({"data": [{"type": "pie", "labels": ["hbo", "wo"], "values": [10, 20]}], "layout": {}})
    nieuw = json.dumps({"data": [{"type": "pie", "labels": ["hbo", "wo"], "values": [10, 25]}], "layout": {}})
    [melding] = _verschil(oud, nieuw)
    assert "wo" in melding
    assert "20 → 25" in melding


def test_ander_aantal_reeksen_wordt_gemeld():
    oud = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {}})
    nieuw = json.dumps(
        {"data": [{"type": "bar", "x": ["2023"], "y": [1]}, {"type": "bar", "x": ["2023"], "y": [2]}], "layout": {}}
    )
    [melding] = _verschil(oud, nieuw)
    assert "aantal reeksen veranderde van 1 naar 2" in melding


def test_onleesbare_figuur_geeft_een_generieke_melding():
    assert _verschil("geen json", "ook geen json") == ["Grafiek 1 is gewijzigd."]


def test_meldingen_blijven_begrensd():
    jaren = [str(j) for j in range(2000, 2020)]
    oud = json.dumps({"data": [{"type": "bar", "x": jaren, "y": list(range(20))}], "layout": {}})
    nieuw = json.dumps({"data": [{"type": "bar", "x": jaren, "y": list(range(1, 21))}], "layout": {}})
    meldingen = _verschil(oud, nieuw)
    assert len(meldingen) == MAX_MELDINGEN + 1
    assert "andere wijzigingen" in meldingen[-1]


def test_alleen_opmaak_gewijzigd_geeft_geen_datamelding():
    oud = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {"title": {"text": "A"}}})
    nieuw = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {"title": {"text": "B"}}})
    assert _verschil(oud, nieuw) == []


def test_float_ruis_geeft_geen_x_naar_x_melding():
    # nl_getal toont beide als "0,3": een melding "0,3 → 0,3" zou de gebruiker misleiden.
    assert _verschil(_figuur([0.3, 1]), _figuur([0.30000000000000004, 1])) == []


def test_verschil_onder_de_getoonde_precisie_wordt_bewust_niet_gemeld():
    # 0,123 en 0,124 tonen beide als "0,1": gelijkheid volgt wat de gebruiker ziet (één decimaal).
    assert _verschil(_figuur([0.123, 1]), _figuur([0.124, 1])) == []


def test_verschil_op_de_getoonde_precisie_wordt_wel_gemeld():
    [melding] = _verschil(_figuur([0.14, 1]), _figuur([0.16, 1]))
    assert "0,1 → 0,2" in melding


def test_geheel_getal_en_bijna_gelijke_float_zijn_gelijk():
    assert _verschil(_figuur([2, 1]), _figuur([2.04, 1])) == []


def test_min_nul_en_nul_zijn_gelijk():
    assert _verschil(_figuur([-0.04, 1]), _figuur([0, 1])) == []


class TestKoppelingOpReceptId:
    """#523: oud en nieuw horen bij elkaar via het recept, nooit via de positie in de lijst."""

    def test_weggevallen_figuur_wordt_niet_met_een_andere_vergeleken(self):
        # De reproductie uit #523: met zip op positie werd B met A vergeleken.
        a = _figuur([9, 9], titel="A", x=["a", "b"])
        b = _figuur([1, 2], titel="B", x=["a", "b"])

        meldingen = figuur_verschillen({"A": a, "B": b}, {"A": a})

        assert meldingen == ["'B' staat niet meer in het dashboard."]

    def test_nieuwe_figuur_wordt_gemeld_zonder_telregel(self):
        fig = _figuur([1, 2])

        meldingen = figuur_verschillen({"A": fig}, {"A": fig, "C": _figuur([3, 4], titel="Extra")})

        assert meldingen == ["'Extra' is nieuw in het dashboard."]
        assert not any("aantal grafieken" in m for m in meldingen)

    def test_volgorde_van_de_mapping_doet_er_niet_toe(self):
        a_oud, a_nieuw = _figuur([1, 2], titel="A"), _figuur([1, 5], titel="A")
        b = _figuur([7, 8], titel="B")

        [melding] = figuur_verschillen({"A": a_oud, "B": b}, {"B": b, "A": a_nieuw})

        assert melding.startswith("'A'")
        assert "2 → 5" in melding

    def test_naam_zonder_titel_telt_de_positie_van_het_recept(self):
        # Recept 2 mislukte en staat aan geen van beide kanten; recept 3 houdt zijn nummer.
        oud = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {}})
        nieuw = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [2]}], "layout": {}})
        a = _figuur([1, 2], titel="A")

        [melding] = figuur_verschillen({"r1": a, "r3": oud}, {"r1": a, "r3": nieuw}, ["r1", "r2", "r3"])

        assert melding.startswith("Grafiek 3, 2023:")

    def test_weggevallen_figuur_zonder_titel_heet_naar_zijn_positie(self):
        zonder_titel = json.dumps({"data": [{"type": "bar", "x": ["2023"], "y": [1]}], "layout": {}})

        meldingen = figuur_verschillen({"r1": _figuur([1, 2]), "r2": zonder_titel}, {"r1": _figuur([1, 2])})

        assert meldingen == ["Grafiek 2 staat niet meer in het dashboard."]


class TestHeatmap:
    def test_gewijzigde_cel_noemt_rij_kolom_en_beide_waarden(self):
        meldingen = _verschil(_heatmap([[1000, 1100], [2000, 2100]]), _heatmap([[1000, 1250], [2000, 2100]]))

        assert len(meldingen) == 1
        [melding] = meldingen
        assert "'Instroom per sector'" in melding
        assert "hbo" in melding and "2024" in melding
        assert "1.100 → 1.250" in melding

    def test_ongewijzigde_heatmap_geeft_geen_meldingen(self):
        z = [[1000, 1100], [2000, 2100]]
        assert _verschil(_heatmap(z), _heatmap(z)) == []
        # Alleen de opmaak anders: wel vergeleken, geen datamelding.
        assert _verschil(_heatmap(z, titel="A"), _heatmap(z, titel="B")) == []

    def test_zonder_labels_telt_de_positie(self):
        [melding] = _verschil(
            _heatmap([[1, 2], [3, 4]], titel=None, labels=False), _heatmap([[1, 2], [5, 4]], titel=None, labels=False)
        )

        assert "rij 2, kolom 1" in melding
        assert "3 → 5" in melding

    def test_een_eendimensionale_z_breekt_de_vergelijking_niet(self):
        # Een 3D-spreiding heeft een z per punt, geen raster: buiten scope, maar geen crash.
        oud = json.dumps({"data": [{"type": "scatter3d", "x": [1], "y": [2], "z": [3]}], "layout": {}})
        nieuw = json.dumps({"data": [{"type": "scatter3d", "x": [1], "y": [2], "z": [4]}], "layout": {}})
        assert isinstance(_verschil(oud, nieuw), list)


class TestDubbeleCategorie:
    def test_tweede_punt_met_dezelfde_categorie_valt_niet_samen_met_het_eerste(self):
        x = ["2024", "2024"]

        meldingen = _verschil(_figuur([1, 2], x=x), _figuur([1, 3], x=x))

        assert len(meldingen) == 1
        [melding] = meldingen
        assert "2024 (2e)" in melding
        assert "2 → 3" in melding

    def test_alleen_het_eerste_punt_gewijzigd(self):
        x = ["2024", "2024"]

        [melding] = _verschil(_figuur([1, 2], x=x), _figuur([5, 2], x=x))

        assert "2024:" in melding and "(2e)" not in melding
        assert "1 → 5" in melding


def test_liggende_staven_vergelijken_de_categorie_op_de_y_as():
    def liggend(x: list) -> str:
        trace = {"type": "bar", "orientation": "h", "y": ["UvA", "VU"], "x": x}
        return json.dumps({"data": [trace], "layout": {"title": {"text": "Gediplomeerden"}}})

    [melding] = _verschil(liggend([14773, 10499]), liggend([14773, 10500]))
    assert "VU: 10.499 → 10.500" in melding


def test_staaf_per_reeks_in_de_oude_vorm_is_gelijk_aan_een_reeks():
    # Tot de leesbare grafieken tekende een uitgelichte staaf een reeks per staaf; een bewaarde
    # grafiek in die vorm is na verversen niet "anders" omdat het er nu één reeks is.
    namen, waarden = ["UvA", "VU"], [14773, 10499]
    oud = json.dumps(
        {
            "data": [{"type": "bar", "name": n, "x": [n], "y": [w]} for n, w in zip(namen, waarden, strict=True)],
            "layout": {},
        }
    )
    nieuw = json.dumps({"data": [{"type": "bar", "orientation": "h", "y": namen, "x": waarden}], "layout": {}})
    assert _verschil(oud, nieuw) == []
    [melding] = _verschil(oud, nieuw.replace("10499", "10500"))
    assert "VU: 10.499 → 10.500" in melding

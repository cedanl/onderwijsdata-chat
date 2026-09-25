"""DUO-sentinels (-1) moeten via élke route naar de store gemaskeerd worden.

De eerdere opzet maskeerde alleen in get_duo_data. Data die via een upload, een replay,
een test of een afgeleide query_data-key in de store belandde bleef ongemaskeerd, en
telde de -1 gewoon mee. Die routes staan hieronder expliciet in de tests.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from tools import store
from tools.duo import (
    _apply_aggregation,
    count_cells,
    get_duo_data,
    mask_sentinels,
    query_data,
    sentinel_notes,
)


@pytest.fixture(autouse=True)
def _schone_store():
    """De store is process-breed; zonder opruimen lekken keys tussen tests door."""
    store.clear()
    yield
    store.clear()


class TestMaskSentinels:
    def test_vervangt_minus_een_door_na(self):
        df = pd.DataFrame({"AANTAL": [100, 200, -1, 300], "NAAM": ["A", "B", "C", "D"]})
        masked, cells = mask_sentinels(df)

        assert pd.isna(masked.loc[2, "AANTAL"])
        assert [masked.loc[i, "AANTAL"] for i in (0, 1, 3)] == [100, 200, 300]
        assert count_cells(cells) == {"AANTAL": 1}
        assert list(cells.index) == [2]

    def test_laat_niet_numerieke_kolommen_ongemoeid(self):
        df = pd.DataFrame({
            "AANTAL": [100, -1, 300],
            "NAAM": ["A", "B", "C"],
            "JAAR": [2021, 2021, 2021],
        })
        masked, _ = mask_sentinels(df)

        assert list(masked["NAAM"]) == ["A", "B", "C"]
        assert list(masked["JAAR"]) == [2021, 2021, 2021]

    def test_gemaskeerde_waarde_is_na_en_geen_nul(self):
        masked, _ = mask_sentinels(pd.DataFrame({"AANTAL": [100, 200, -1]}))

        assert pd.isna(masked.loc[2, "AANTAL"])
        # Zou de cel stilletjes 0 worden, dan was het gemiddelde 100 in plaats van 150.
        assert masked["AANTAL"].mean() == 150

    def test_telt_meerdere_sentinels_per_kolom(self):
        df = pd.DataFrame({"AANTAL": [-1, 100, -1, 200, -1]})
        masked, cells = mask_sentinels(df)

        assert [pd.isna(masked.loc[i, "AANTAL"]) for i in (0, 2, 4)] == [True] * 3
        assert count_cells(cells) == {"AANTAL": 3}

    def test_laat_de_bron_dataframe_ongewijzigd(self):
        df = pd.DataFrame({"AANTAL": [100, -1]})
        mask_sentinels(df)

        assert df.loc[1, "AANTAL"] == -1

    def test_is_idempotent(self):
        eerste, cells_1 = mask_sentinels(pd.DataFrame({"AANTAL": [100, -1]}))
        _, cells_2 = mask_sentinels(eerste)

        assert count_cells(cells_1) == {"AANTAL": 1}
        assert count_cells(cells_2) == {}

    def test_maskeert_geen_kolom_waarin_min_een_een_meetwaarde_is(self):
        """-1 in een mutatie/saldo-kolom is een echte waarde, geen onderdrukte cel."""
        df = pd.DataFrame({"SALDO_MUTATIE": [50, -1, 30], "AANTAL": [10, -1, 20]})
        masked, cells = mask_sentinels(df)

        assert masked.loc[1, "SALDO_MUTATIE"] == -1
        assert pd.isna(masked.loc[1, "AANTAL"])
        assert count_cells(cells) == {"AANTAL": 1}

    def test_maskeert_pivot_telkolommen_zonder_aantal_prefix(self):
        """DUO kent pivot-datasets waarin de telling in de kolomnaam zit."""
        df = pd.DataFrame({"DIPMAN2023": [40, -1], "JAAR_2022": [15, -1]})
        masked, cells = mask_sentinels(df)

        assert pd.isna(masked.loc[1, "DIPMAN2023"])
        assert pd.isna(masked.loc[1, "JAAR_2022"])
        assert count_cells(cells) == {"DIPMAN2023": 1, "JAAR_2022": 1}


class TestStoreRoutes:
    """Elke route die een `duo:`-key in de store zet, moet gemaskeerde data opleveren."""

    def test_directe_store_put_wordt_gemaskeerd(self):
        store.put("duo:direct", pd.DataFrame({"GROEP": ["A", "A"], "AANTAL": [100, -1]}))

        opgeslagen = store.get("duo:direct")
        assert pd.isna(opgeslagen.loc[1, "AANTAL"])

    def test_niet_duo_keys_blijven_onaangeroerd(self):
        store.put("cbs:iets", pd.DataFrame({"AANTAL": [100, -1]}))

        assert store.get("cbs:iets").loc[1, "AANTAL"] == -1

    def test_aggregatie_na_directe_put_telt_sentinel_niet_mee(self):
        store.put("duo:direct", pd.DataFrame({
            "GROEP": ["A", "A", "B", "B"],
            "AANTAL": [100, -1, 50, 60],
        }))

        result = json.loads(query_data(
            "duo:direct", group_by=["GROEP"], aggregate={"AANTAL": "sum"},
        ))
        per_groep = {r["GROEP"]: r["AANTAL"] for r in result["rijen"]}

        assert per_groep["A"] == 100
        assert per_groep["B"] == 110

    def test_afgeleide_key_erft_gemaskeerde_data(self):
        store.put("duo:bron", pd.DataFrame({
            "GROEP": ["A", "A"], "AANTAL": [100, -1],
        }))

        tussenstap = json.loads(query_data("duo:bron", columns=["GROEP", "AANTAL"]))
        result = json.loads(query_data(
            tussenstap["data_key"], group_by=["GROEP"], aggregate={"AANTAL": "sum"},
        ))

        assert result["rijen"][0]["AANTAL"] == 100


class TestMelding:
    """Onderdrukte cellen maken een totaal een ondergrens — dat moet de gebruiker zien."""

    def test_query_data_meldt_uitgesloten_cellen(self):
        store.put("duo:melding", pd.DataFrame({
            "GROEP": ["A", "A"], "AANTAL": [100, -1],
        }))

        result = json.loads(query_data(
            "duo:melding", group_by=["GROEP"], aggregate={"AANTAL": "sum"},
        ))

        assert "databewerking" in result
        assert "ondergrens" in result["databewerking"][0]

    def test_geen_melding_zonder_onderdrukte_cellen(self):
        store.put("duo:schoon", pd.DataFrame({"GROEP": ["A"], "AANTAL": [100]}))

        result = json.loads(query_data(
            "duo:schoon", group_by=["GROEP"], aggregate={"AANTAL": "sum"},
        ))

        assert "databewerking" not in result

    def test_melding_reist_mee_naar_afgeleide_key(self):
        store.put("duo:bron", pd.DataFrame({
            "GROEP": ["A", "A"], "AANTAL": [100, -1],
        }))

        tussenstap = json.loads(query_data("duo:bron", columns=["GROEP", "AANTAL"]))
        result = json.loads(query_data(
            tussenstap["data_key"], group_by=["GROEP"], aggregate={"AANTAL": "sum"},
        ))

        assert "databewerking" in result

    def test_get_duo_data_meldt_telling_als_resourcebreed(self):
        # Live-audit 6: de resourcebrede telling (101 in p01hoinges) werd aan gefilterde
        # totalen zonder -1 geplakt als "ondergrens". Die kwalificatie hoort bij query_data (#179).
        df = pd.DataFrame({"INSTELLING": ["HU", "X"], "AANTAL": [100, -1]})
        with patch("tools.duo._duo.load", return_value=df):
            result = json.loads(get_duo_data("resourcebreed", 0))

        [melding] = result["databewerking"]
        assert "hele resource" in melding
        assert "ondergrens" not in melding

    def test_sentinel_notes_is_leeg_zonder_tellingen(self):
        assert sentinel_notes({}) == []


class TestAggregatie:
    def test_sommeert_zonder_de_gemaskeerde_cellen(self):
        df = pd.DataFrame({"GROEP": ["A", "A", "A"], "AANTAL": [100.0, 200.0, pd.NA]})

        result = _apply_aggregation(df, group_by=["GROEP"], aggregate={"AANTAL": "sum"})

        assert float(result.loc[0, "AANTAL"]) == 300.0

    def test_sluit_sentinels_uit_bij_meerdere_groepen(self):
        df = pd.DataFrame({
            "GROEP_A": ["X", "X", "X", "Y", "Y"],
            "GROEP_B": ["1", "1", "1", "2", "2"],
            "AANTAL": [100.0, 200.0, pd.NA, 150.0, pd.NA],
        })

        result = _apply_aggregation(
            df, group_by=["GROEP_A", "GROEP_B"], aggregate={"AANTAL": "sum"},
        )
        waarde = {(r["GROEP_A"], r["GROEP_B"]): float(r["AANTAL"]) for _, r in result.iterrows()}

        assert waarde[("X", "1")] == 300.0
        assert waarde[("Y", "2")] == 150.0


class TestMeldingPerSelectie:
    """De melding hoort bij de geselecteerde rijen, niet bij de hele dataset (#171).

    Live-audit 5: de HU-voltijdreeks (0 onderdrukte cellen) werd 'een ondergrens'
    genoemd omdat p01hoinges als geheel 101 cellen met -1 heeft.
    """

    @pytest.fixture(autouse=True)
    def _bron(self):
        store.put("duo:p01:3", pd.DataFrame({
            "INSTELLING": ["HU", "HU", "X", "X", "X"],
            "JAAR": [2024, 2025, 2024, 2025, 2025],
            "AANTAL": [27135, 26370, -1, 40, -1],
        }))

    def _som(self, key, **kwargs):
        return json.loads(query_data(key, group_by=["JAAR"], aggregate={"AANTAL": "sum"}, **kwargs))

    def test_schone_selectie_krijgt_geen_melding(self):
        result = self._som("duo:p01:3", filters={"INSTELLING": "HU"})

        assert "databewerking" not in result

    def test_melding_telt_alleen_de_selectie(self):
        store.put("duo:groot", pd.DataFrame({
            "INSTELLING": ["X", "X", "Y"], "JAAR": [2025, 2025, 2025], "AANTAL": [-1, -1, -1],
        }))

        result = self._som("duo:groot", filters={"INSTELLING": "X"})

        assert result["databewerking"][0].startswith("2 cellen")

    def test_zonder_filter_telt_de_hele_dataset(self):
        result = self._som("duo:p01:3")

        assert result["databewerking"][0].startswith("2 cellen")

    def test_afgeleide_schone_selectie_blijft_schoon(self):
        tussenstap = json.loads(query_data("duo:p01:3", filters={"INSTELLING": "HU"}))

        result = self._som(tussenstap["data_key"])

        assert "databewerking" not in result

    def test_geaggregeerde_key_houdt_telling_per_groep(self):
        # Na aggregeren zijn de NA's weg; de telling moet per groep meereizen.
        store.put("duo:jaren", pd.DataFrame({
            "JAAR": [2024, 2024, 2025, 2025], "AANTAL": [10, 20, -1, 5],
        }))
        per_jaar = self._som("duo:jaren")

        schoon = self._som(per_jaar["data_key"], filters={"JAAR": 2024})
        vuil = self._som(per_jaar["data_key"], filters={"JAAR": 2025})

        assert "databewerking" not in schoon
        assert vuil["databewerking"][0].startswith("1 cellen")

    def test_weggeselecteerde_kolom_neemt_geen_melding_mee(self):
        tussenstap = json.loads(query_data("duo:p01:3", columns=["INSTELLING", "JAAR"]))

        result = json.loads(query_data(
            tussenstap["data_key"], group_by=["INSTELLING"], aggregate={"JAAR": "count"},
        ))

        assert "databewerking" not in result

    def test_groeperen_op_kolom_met_sentinels_crasht_niet(self):
        store.put("duo:codes", pd.DataFrame({"CODE": [1, -1, 1], "AANTAL": [5, 6, -1]}))

        result = json.loads(query_data("duo:codes", group_by=["CODE"], aggregate={"AANTAL": "sum"}))

        assert sorted(result["databewerking"]) == sentinel_notes({"AANTAL": 1, "CODE": 1})

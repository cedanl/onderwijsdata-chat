"""run_analysis: een leesbare fout, geen serverpaden en een begrensde uitvoer (#629)."""

import json

import pandas as pd
import pytest

from tools import analysis, sandbox, store


def _in_sandbox(code: str, df: pd.DataFrame | None = None) -> sandbox.Uitkomst:
    return sandbox.voer_uit(code, df if df is not None else pd.DataFrame({"N": [1]}), {})


# --- 1. Deling door nul met numpy-scalars ---


@pytest.mark.parametrize(
    "code",
    [
        "result = df['BBL'].sum() / df['BOLDT'].sum() * 100",
        "result = df['BOLDT'].sum() / df['BOLDT'].sum()",
        "result = np.float64(5) / np.float64(0)",
    ],
)
def test_deling_door_nul_geeft_een_leesbare_fout(code):
    uitkomst = _in_sandbox(code, pd.DataFrame({"BBL": [3, 4], "BOLDT": [0, 0]}))
    assert uitkomst.fout
    assert "__import__" not in uitkomst.fout
    assert "FloatingPointError" in uitkomst.fout
    assert "noemer" in uitkomst.fout  # de uitleg voor het model: wat er mis is en waar te kijken


def test_deling_van_kolommen_door_nul_blijft_inf():
    # pandas rekent zelf met inf en NaN: een kolomdeling mag niet stoppen.
    uitkomst = _in_sandbox(
        "result = (df['BBL'] / df['BOLDT']).tolist()", pd.DataFrame({"BBL": [3, 0], "BOLDT": [0, 0]})
    )
    assert uitkomst.fout is None
    assert len(uitkomst.result) == 2


def test_gewone_float_deling_door_nul_blijft_zerodivisionerror():
    uitkomst = _in_sandbox("result = float(df['N'].sum()) / 0")
    assert uitkomst.fout and "ZeroDivisionError" in uitkomst.fout


def test_een_waarschuwing_stopt_het_script_niet():
    # nanmean van alleen NaN geeft een RuntimeWarning en NaN: het script gaat door.
    uitkomst = _in_sandbox("result = float(np.nanmean(np.array([np.nan])))")
    assert uitkomst.fout is None


# --- 2. De fout bevat geen serverpaden ---


def test_fout_toont_de_scriptregel_en_de_laatste_regel_zonder_paden():
    uitkomst = _in_sandbox("x = 1\nresult = df['BESTAAT_NIET']")
    assert uitkomst.fout
    assert 'File "<analysis>", line 2' in uitkomst.fout
    assert "result = df['BESTAAT_NIET']" in uitkomst.fout
    assert uitkomst.fout.strip().endswith("KeyError: 'BESTAAT_NIET'")
    assert "site-packages" not in uitkomst.fout
    assert ".py" not in uitkomst.fout
    assert len(uitkomst.fout) < 400


def test_fout_in_astype_is_kort_en_zonder_paden():
    df = pd.DataFrame({"N": [1.0, None]})
    uitkomst = _in_sandbox("result = df['N'].astype(int).tolist()", df)
    assert uitkomst.fout
    assert "site-packages" not in uitkomst.fout and "/" not in uitkomst.fout.replace("<analysis>", "")
    assert len(uitkomst.fout) < 700


def test_syntaxfout_in_het_kindproces_heeft_geen_pad():
    uitkomst = _in_sandbox("result = (")
    assert uitkomst.fout and "SyntaxError" in uitkomst.fout
    assert "site-packages" not in uitkomst.fout


# --- 3. Begrensde uitvoer ---


def test_een_te_grote_uitkomst_wordt_geweigerd_met_uitleg():
    breed = pd.DataFrame({k: ["x" * 1000] * 3000 for k in "abcde"})  # ± 15 MB als JSON
    uitkomst = _in_sandbox("result = df", breed)
    assert uitkomst.fout
    assert "te groot" in uitkomst.fout
    assert uitkomst.result is None


def _rijen(code: str, data_key: str) -> dict:
    uitkomst = analysis.run_analysis(code=code, data_key=data_key)
    assert isinstance(uitkomst, str)
    return json.loads(uitkomst)


def _put(key: str, n: int) -> None:
    store.put(
        key, pd.DataFrame({"jaar": range(n), "n": range(n)}), store.KeyMeta(bron="test", dataset=key, volledig=True)
    )


def test_een_grote_tabel_als_uitkomst_geeft_een_begrensd_antwoord_met_totaal():
    _put("test:groot629", 1200)
    uit = _rijen("result = df", "test:groot629")
    assert uit["totaal_rijen"] == 1200
    assert len(uit["rijen"]) == 500  # 2 kolommen: het maximum van query_data
    assert "Eerste 500 van 1200 rijen" in uit["waarschuwing"]
    assert "query_data" in uit["waarschuwing"]
    # De volledige tabel staat onder de nieuwe key, voor query_data.
    assert len(store.readonly(uit["data_key"])) == 1200


def test_een_kleine_tabel_blijft_onverkort_en_zonder_totaal():
    _put("test:klein629", 40)
    uit = _rijen("result = df", "test:klein629")
    assert len(uit["rijen"]) == 40
    assert "totaal_rijen" not in uit

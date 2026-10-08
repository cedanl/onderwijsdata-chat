"""run_analysis draait modelgeschreven Python in een eigen, afgeschermd proces (#410, #62).

Twee lagen: een AST-controle weigert het script vooraf, en het kindproces kan ook
zonder die controle niets bereiken (geen omgevingsvariabelen, bestanden, netwerk of
processen). De sandboxtests hieronder roepen het kindproces direct aan om die tweede
laag los van de eerste te toetsen.
"""

import json
import os
import time

import pandas as pd
import pytest

from agent import grounding
from tools import analysis, sandbox, store


def _put(key: str, data: list[dict]) -> None:
    store.put(key, pd.DataFrame(data), store.KeyMeta(bron="test", dataset=key, volledig=True))


@pytest.fixture
def data():
    _put("test:iso", [{"N": 1200}, {"N": 3400}])
    return "test:iso"


def run_analysis(code: str, data_key: str) -> str:
    uitkomst = analysis.run_analysis(code=code, data_key=data_key)
    assert isinstance(uitkomst, str)
    return uitkomst


def _in_sandbox(code: str, df: pd.DataFrame | None = None) -> sandbox.Uitkomst:
    """Het kindproces zonder de AST-controle ervoor: de tweede laag op zichzelf."""
    return sandbox.voer_uit(code, df if df is not None else pd.DataFrame({"N": [1]}), {})


# --- Probe 1: __globals__ (CH-02) ---


def test_globals_probe_wordt_geweigerd(data):
    uitkomst = run_analysis(code="result = df.__init__.__globals__['os'].getpid()", data_key=data)
    assert "niet toegestaan" in uitkomst.lower()
    assert str(os.getpid()) not in uitkomst


@pytest.mark.parametrize(
    "code",
    [
        "result = len(df.__class__.__mro__)",
        "result = (x for x in df).gi_frame.f_globals",
        "result = df.query('N.__class__')",
        "result = '{0.__class__}'.format(df)",
        "result = len(store_get(df.columns[0]))",
    ],
)
def test_ast_laag_weigert_ontsnappingsroutes(data, code):
    assert "niet toegestaan" in run_analysis(code=code, data_key=data).lower()


def test_kindproces_draait_los_van_de_server():
    uitkomst = _in_sandbox("result = pd.io.common.os.getpid()")
    assert uitkomst.fout is None
    assert uitkomst.result != os.getpid()


def test_kindproces_ziet_geen_omgevingsvariabelen_van_de_server(monkeypatch):
    monkeypatch.setenv("GEHEIM_410", "lek")
    uitkomst = _in_sandbox("result = dict(pd.io.common.os.environ)")
    assert uitkomst.fout is None
    assert "GEHEIM_410" not in uitkomst.result


@pytest.mark.parametrize(
    "code",
    [
        "result = pd.read_csv('/etc/passwd')",
        "result = pd.io.common.os.listdir('/')",
        "df.to_csv('uit.csv')\nresult = 1",
        "result = pd.io.common.os.system('true')",
        "result = pd.read_csv('http://127.0.0.1:9/x.csv')",
    ],
)
def test_kindproces_heeft_geen_bestanden_netwerk_of_processen(code):
    uitkomst = _in_sandbox(code)
    assert uitkomst.fout is not None
    assert "sandbox" in uitkomst.fout


def test_bestand_lezen_via_run_analysis_wordt_geweigerd(data):
    # #62: pd.read_csv('/etc/passwd')-variant.
    uitkomst = run_analysis(code="result = pd.read_csv('/etc/passwd') if len(df) else 0", data_key=data)
    assert "root:" not in uitkomst
    assert "sandbox" in uitkomst


def test_oneindige_lus_wordt_echt_gestopt(data, monkeypatch):
    monkeypatch.setattr(sandbox, "TIMEOUT_SECONDS", 2)
    start = time.monotonic()
    uitkomst = run_analysis(code="while len(df):\n    pass", data_key=data)
    assert "langer dan 2 seconden" in uitkomst
    assert time.monotonic() - start < 6


# --- Probe 2: een getal dat het script zelf typte is geen bewijs ---


@pytest.mark.parametrize(
    "code",
    [
        "result = 987654 + int(df.shape[0] * 0)",
        "result = 987650 + 4 + int(df.shape[0] * 0)",
        "result = int('987654') + int(df.shape[0] * 0)",
        "result = {'totaal': 987654, 'n': len(df)}",
        "result = df.assign(T=987654)",
        # CH-27: een constante via een variabele, of df gelezen maar niet gebruikt.
        "a = 987650\nb = 4\nresult = a + b + len(df) * 0",
        "a = 987650\nresult = a + 4 + int(df['N'].sum()) * 0",
        "x = df['N'].sum()\nresult = 987654",
        "basis = {'n': 987650}\nresult = basis['n'] + 4 + len(df) * 0",
        "result = f'totaal {987650 + 4}' if len(df) else ''",
    ],
)
def test_getal_uit_het_script_telt_niet_als_bron(data, code):
    uitkomst = run_analysis(code=code, data_key=data)
    assert grounding.unverified("Er zijn 987.654 studenten.", [uitkomst]) == ["987.654"]


def test_percentage_uit_het_script_telt_niet_als_bron(data):
    uitkomst = run_analysis(code="result = 12.5 + len(df) * 0", data_key=data)
    assert grounding.unverified("Dat is 12,5%.", [uitkomst]) == ["12,5%"]


def test_percentage_via_een_variabele_telt_niet_als_bron(data):
    uitkomst = run_analysis(code="p = 12.5\nresult = p + len(df) * 0", data_key=data)
    assert grounding.unverified("Dat is 12,5%.", [uitkomst]) == ["12,5%"]


@pytest.mark.parametrize(
    ("code", "tekst"),
    [
        ("result = int(df['N'].sum()) + 0", "Er zijn 4.600 studenten."),  # som
        ("result = int(df['N'].iloc[1] - df['N'].iloc[0])", "Een verschil van 2.200 studenten."),  # verschil
        ("result = round(df['N'].iloc[0] / df['N'].sum() * 100, 1)", "Dat is 26,1%."),  # percentage
        ("totaal = df['N'].sum()\nresult = int(totaal)", "Er zijn 4.600 studenten."),  # via een variabele
        ("result = len(df) * 1000 + 0", "Dat zijn 2000 rijen."),  # een telling hangt ook van de data af
    ],
)
def test_een_afleiding_uit_de_data_blijft_bewijs(data, code, tekst):
    uitkomst = run_analysis(code=code, data_key=data)
    assert grounding.unverified(tekst, [uitkomst]) == []


def test_scriptconstanten_staan_bij_het_resultaat(data):
    parsed = json.loads(run_analysis(code="result = {'totaal': int(df['N'].sum()), 'drempel': 1000}", data_key=data))
    assert parsed["resultaat"] == {"totaal": 4600, "drempel": 1000}
    assert parsed["scriptconstanten"] == [1000]


def test_een_getal_uit_de_invoer_is_geen_scriptconstante(data):
    """De invoer is zelf bewijs: een opgezochte celwaarde hoort niet bij de scriptconstanten."""
    parsed = json.loads(run_analysis(code="result = {'max': int(df['N'].max()), 'vast': 1200}", data_key=data))
    assert "scriptconstanten" not in parsed

"""De store-key van een analyse volgt de inhoud, niet het geheugenadres (#62, uit #47).

`analysis:{id(df)}` gaf in de Arena-audit drie keys voor drie identieke runs: caching en
replay braken, en metadata erven (#186) hing aan een toevallig adres.
"""

import json

import pandas as pd

from tools import store
from tools.analysis import run_analysis

_SCRIPT = "result = df.groupby('JAAR')['N'].sum().reset_index().to_dict(orient='records')"


def _put(key: str, data: list[dict]) -> None:
    store.put(key, pd.DataFrame(data), store.KeyMeta(bron="test", dataset=key, volledig=True))


def _key(code: str = _SCRIPT, data_key: str = "test:an") -> str:
    result = run_analysis(code=code, data_key=data_key)
    assert isinstance(result, str)
    return json.loads(result)["data_key"]


def test_dezelfde_analyse_geeft_dezelfde_key():
    _put("test:an", [{"JAAR": 2021, "N": 10}, {"JAAR": 2022, "N": 30}])
    assert _key() == _key() == _key()


def test_een_ander_resultaat_geeft_een_andere_key():
    _put("test:an", [{"JAAR": 2021, "N": 10}, {"JAAR": 2022, "N": 30}])
    eerste = _key()
    _put("test:an", [{"JAAR": 2021, "N": 11}, {"JAAR": 2022, "N": 30}])
    assert _key() != eerste


def test_dezelfde_rijen_uit_een_andere_bron_krijgen_een_andere_key():
    """De herkomst hoort bij de key: dezelfde rijen uit een andere bron zijn een andere afleiding."""
    _put("test:an", [{"JAAR": 2021, "N": 10}])
    _put("test:ander", [{"JAAR": 2021, "N": 10}])
    assert _key(data_key="test:an") != _key(data_key="test:ander")


def test_een_cel_met_een_lijst_geeft_ook_een_key():
    _put("test:an", [{"JAAR": 2021, "N": 10}])
    assert _key("result = [{'JAAR': int(df['JAAR'][0]), 'CODES': ['a', 'b']}]").startswith("analysis:")

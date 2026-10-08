"""Drie uitkomsten van de afhankelijkheidscontrole, niet twee (CH-27, #456).

Een mislukte verstoringsproef gaf hetzelfde signaal als 'alles hangt van de data af',
en dus bronbewijs. Nu is 'niet vast te stellen' een eigen uitkomst, en fail-closed.
"""

import pandas as pd

from tools.afhankelijkheid import AFHANKELIJK, ONAFHANKELIJK, ONBEPAALD, toets

_DF = pd.DataFrame({"N": [1200, 3400]})


def test_een_afleiding_uit_de_data_is_afhankelijk():
    uitkomst = toets("result = int(df['N'].sum())", _DF, {}, 4600)
    assert (uitkomst.soort, uitkomst.constanten) == (AFHANKELIJK, ())


def test_een_getypt_getal_is_onafhankelijk():
    uitkomst = toets(
        "result = {'totaal': int(df['N'].sum()), 'vast': 987654}", _DF, {}, {"totaal": 4600, "vast": 987654}
    )
    assert (uitkomst.soort, uitkomst.constanten) == (ONAFHANKELIJK, (987654,))


def test_een_mislukte_verstoringsproef_is_niet_vast_te_stellen_en_telt_niet():
    code = "rij = df[df['N'] == 1200].iloc[0]\nresult = {'n': int(rij['N']), 'x': int(rij['N']) * 823 + 54}"
    uitkomst = toets(code, _DF, {}, {"n": 1200, "x": 987654})
    assert uitkomst.soort == ONBEPAALD
    assert uitkomst.constanten == (987654,)  # 1200 staat in de invoer en blijft bewijs


def test_een_geerfde_constante_blijft_onafhankelijk():
    """Een waarde die een eerdere stap afkeurde, staat nu in de invoer; dat maakt haar geen bewijs."""
    df = pd.DataFrame({"T": [987654], "n": [2]})
    uitkomst = toets("result = int(df['T'].iloc[0])", df, {}, 987654, geerfd=(987654,))
    assert uitkomst.constanten == (987654,)

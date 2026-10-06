"""Een oorzaak is gedekt als een andere bron haar aantoont dan die van het effect (#225).

Avans: het verschil tussen personen (p01hoinges) en inschrijvingen (p03hoinges) is bewezen,
"meervoudige inschrijvingen" als oorzaak niet; de getallen erbij zijn die van het effect zelf.
HU: een daling uit p01hoinges, verklaard met het aantal 18-jarigen uit een CBS-tabel, is wel
gedekt: de oorzaak rust op een eigen bron. Dezelfde regel geldt voor chat en rapport.
"""

import json

import pandas as pd
import pytest

from agent.beweringen import ongedekte_oorzaak
from agent.report import ReportSpec
from agent.report_checks import report_problems
from tools import store
from tools.store import KeyMeta

_HU = "duo:p01hoinges:hu"
_JONGEREN = "cbs:37296ned:jongeren"
_AVANS_PERSONEN = "duo:p01hoinges:avans"
_AVANS_INSCHRIJVINGEN = "duo:p03hoinges:avans"

_DATA = {
    _HU: ("p01hoinges", {"STUDIEJAAR": [2021, 2025], "AANTAL": [28355, 26370]}),
    _JONGEREN: ("37296ned", {"Perioden": ["2021JJ00", "2025JJ00"], "Jongeren18": [210450, 198320]}),
    _AVANS_PERSONEN: ("p01hoinges", {"STUDIEJAAR": [2024], "AANTAL": [24169]}),
    _AVANS_INSCHRIJVINGEN: ("p03hoinges", {"STUDIEJAAR": [2024], "AANTAL": [24740]}),
}


@pytest.fixture(autouse=True)
def _store():
    store.clear()
    for key, (dataset, kolommen) in _DATA.items():
        store.put(key, pd.DataFrame(kolommen), KeyMeta(bron=key.split(":")[0], dataset=dataset))
    yield
    store.clear()


def _resultaat(key: str) -> str:
    return json.dumps({"data_key": key, "rijen": store.get(key).to_dict("records")})


_HU_VERKLAARD = (
    "Het aantal daalde van 28.355 in 2021 naar 26.370 in 2025. "
    "Dit komt doordat het aantal 18-jarigen daalde van 210.450 naar 198.320."
)
_AVANS = (
    "Avans had 24.169 personen en 24.740 inschrijvingen. "
    "Het verschil komt doordat studenten meervoudig ingeschreven staan (24.740 tegen 24.169)."
)


def test_oorzaak_uit_een_tweede_bron_is_gedekt():
    assert ongedekte_oorzaak(_HU_VERKLAARD, [_resultaat(_HU), _resultaat(_JONGEREN)]) == []


def test_zonder_die_tweede_bron_is_dezelfde_oorzaak_ongedekt():
    assert len(ongedekte_oorzaak(_HU_VERKLAARD, [_resultaat(_HU)])) == 1


def test_getallen_van_het_effect_dekken_de_oorzaak_niet():
    beurt = [_resultaat(_AVANS_PERSONEN), _resultaat(_AVANS_INSCHRIJVINGEN)]
    assert len(ongedekte_oorzaak(_AVANS, beurt)) == 1


def _rapport(conclusie: str) -> ReportSpec:
    return ReportSpec(
        title="Avans",
        onderzoeksvraag="Hoeveel studenten heeft Avans?",
        beantwoordt=["Personen en inschrijvingen 2024"],
        conclusie=conclusie,
    )


def _oorzaakproblemen(problemen: list) -> list:
    return [p for p in problemen if "oorzaak" in str(p)]


def test_rapport_krijgt_geen_ongedekte_oorzaak_voor_het_avans_verschil():
    beurt = [_resultaat(_AVANS_PERSONEN), _resultaat(_AVANS_INSCHRIJVINGEN)]
    assert len(_oorzaakproblemen(report_problems(_rapport(_AVANS), [], beurt))) == 1


def test_rapport_mag_zeggen_dat_de_oorzaak_niet_vast_te_stellen_is():
    conclusie = (
        "Avans had 24.169 personen en 24.740 inschrijvingen; de oorzaak is met deze gegevens niet vast te stellen."
    )
    beurt = [_resultaat(_AVANS_PERSONEN), _resultaat(_AVANS_INSCHRIJVINGEN)]
    assert _oorzaakproblemen(report_problems(_rapport(conclusie), [], beurt)) == []


def test_rapport_houdt_een_gedekte_verklaring_uit_de_datasetcontext():
    """Het rapport ziet de geladen datasets als één context, niet als losse toolresultaten."""
    context = json.dumps(
        {"datasets": [{"data_key": k, "voorbeelden": store.get(k).to_dict("records")} for k in (_HU, _JONGEREN)]}
    )
    assert _oorzaakproblemen(report_problems(_rapport(_HU_VERKLAARD), [], [context])) == []

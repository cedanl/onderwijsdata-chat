"""Een instructie staat één keer in de systeemprompt (#847): kopieën kosten tokens en lopen uit elkaar."""

import re

from prompts import SYSTEM_PROMPT


def test_het_periodeformaat_staat_een_keer():
    assert SYSTEM_PROMPT.count("`2023KW01`") == 1


def test_dataset_details_voor_de_beste_kandidaten_staat_een_keer():
    assert len(re.findall(r"top 1-3|één tot drie", SYSTEM_PROMPT)) == 1


def test_de_kop_over_periodes_volgt_het_selectieschema():
    # Sinds ADR-006 bouwt de server de filter; het model geeft schooljaren of periodecodes in `selectie`.
    assert "Perioden-filters bouwen" not in SYSTEM_PROMPT

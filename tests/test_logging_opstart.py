"""Logregels en startfouten: JSON met tijdzone, uvicorn in dezelfde vorm, geen toegangslog (#1186).

Het log van een SDP-omgeving gaat naar een logaggregator: elke regel moet JSON zijn, met een tijdstempel die een zone
noemt, en het toegangslog van uvicorn (client-adres, pad met gespreks- en rapport-ID's) hoort er niet in.
"""

import json
import logging
from datetime import datetime, timedelta

import logging_config


def _record(bericht: str = "hallo") -> logging.LogRecord:
    return logging.LogRecord("x", logging.INFO, __file__, 1, bericht, None, None)


# --- #1153: tijdstempel met tijdzone ---


def test_json_tijdstempel_noemt_de_tijdzone():
    tijd = datetime.fromisoformat(json.loads(logging_config.JSONFormatter().format(_record()))["timestamp"])
    assert tijd.utcoffset() == timedelta(0)


def test_json_tijdstempel_volgt_het_moment_van_de_regel():
    record = _record()
    record.created = 1_700_000_000.5
    stempel = json.loads(logging_config.JSONFormatter().format(record))["timestamp"]
    assert stempel == "2023-11-14T22:13:20.500000+00:00"


def test_de_code_gebruikt_geen_utcnow_meer():
    bron = logging_config.__file__
    with open(bron, encoding="utf-8") as f:
        assert "utcnow" not in f.read()

"""Bron-ping (#627): één aanroep per bron door de toollaag, gepland in CI, zonder LLM.

De RIO-uitval van 19-10-2026 (API v2 verwijderd, HTTP 410) viel pas op in een echte chatbeurt: pytest mockt de
bronnen en /health toetst geen bron. Het script en de geplande job maken zo'n uitval binnen een week zichtbaar.
"""

import json
from pathlib import Path

import pytest
import yaml

from scripts import bronping

ROOT = Path(__file__).resolve().parent.parent


def _ping(id: str = "cbs-test", bron: str = "cbs", uitkomst: str | dict = "", bewijs=None) -> bronping.Ping:
    return bronping.Ping(
        id,
        bron,
        "testping",
        haal=lambda: uitkomst,
        bewijs=bewijs or (lambda u: None),
    )


# --- de lijst -------------------------------------------------------------------------


def test_elke_bron_van_de_chat_heeft_een_ping():
    assert {p.bron for p in bronping.PINGS} == {"cbs", "duo", "rio", "kaart"}
    assert len({p.id for p in bronping.PINGS}) == len(bronping.PINGS)


# --- beoordelen -----------------------------------------------------------------------


def test_een_gecodeerde_bronfout_is_een_fout_met_de_tekst_van_de_tool():
    uitslag = bronping.beoordeel(_ping(), "Fout (bron_weigert): RIO weigerde de aanvraag (HTTP 410).")
    assert not uitslag.ok
    assert "HTTP 410" in uitslag.detail


def test_een_platte_tekst_zonder_data_is_een_fout():
    uitslag = bronping.beoordeel(_ping(), "Dataset 'x' valt buiten de scope van de chat.")
    assert not uitslag.ok
    assert "buiten de scope" in uitslag.detail


def test_een_uitkomst_met_bewijs_is_ok():
    uitslag = bronping.beoordeel(_ping(), json.dumps({"data_key": "cbs:85423NED:abc", "totaal_rijen": 1620}))
    assert uitslag.ok
    assert uitslag.detail == ""


def test_een_uitkomst_zonder_het_verwachte_bewijs_is_een_fout():
    ping = _ping(bewijs=lambda u: "geen rijen" if not u.get("totaal_rijen") else None)
    uitslag = bronping.beoordeel(ping, json.dumps({"data_key": "cbs:85423NED:abc", "totaal_rijen": 0}))
    assert not uitslag.ok
    assert uitslag.detail == "geen rijen"


def test_een_dict_zoals_de_geojson_wordt_direct_beoordeeld():
    ping = _ping(bron="kaart", bewijs=lambda u: None if len(u.get("features", [])) >= 12 else "te weinig vormen")
    assert bronping.beoordeel(ping, {"features": [{}] * 12}).ok
    assert bronping.beoordeel(ping, {"features": []}).detail == "te weinig vormen"


def test_een_exception_in_de_tool_is_een_fout_met_het_type():
    def kapot():
        raise TimeoutError("te laat")

    uitslag = bronping.ping(bronping.Ping("rio-test", "rio", "t", haal=kapot, bewijs=lambda u: None))
    assert not uitslag.ok
    assert "TimeoutError" in uitslag.detail and "te laat" in uitslag.detail


# --- het script -----------------------------------------------------------------------


def test_alles_ok_geeft_exit_0_en_een_regel_per_bron(capsys, monkeypatch):
    pings = (
        _ping("cbs-a", "cbs", json.dumps({"totaal_rijen": 3})),
        _ping("duo-b", "duo", json.dumps({"totaal_rijen": 4})),
    )
    monkeypatch.setattr(bronping, "PINGS", pings)

    assert bronping.main([]) == 0
    uit = capsys.readouterr().out
    assert "cbs-a" in uit and "duo-b" in uit
    assert "alle 2 bronnen antwoorden" in uit


def test_een_falende_bron_geeft_exit_1_en_de_andere_staan_toch_in_het_rapport(capsys, monkeypatch):
    pings = (
        _ping("cbs-a", "cbs", json.dumps({"totaal_rijen": 3})),
        _ping("rio-b", "rio", "Fout (bron_weigert): RIO weigerde de aanvraag (HTTP 410)."),
    )
    monkeypatch.setattr(bronping, "PINGS", pings)

    assert bronping.main([]) == 1
    uit = capsys.readouterr().out
    assert "cbs-a" in uit  # de bron die wel antwoordde staat erbij
    assert "1 van 2 bronnen antwoordt niet" in uit
    assert "HTTP 410" in uit


def test_alleen_beperkt_tot_de_genoemde_bronnen(capsys, monkeypatch):
    pings = (
        _ping("cbs-a", "cbs", json.dumps({"totaal_rijen": 3})),
        _ping("rio-b", "rio", "Fout (bron_weigert): RIO weigerde de aanvraag (HTTP 410)."),
    )
    monkeypatch.setattr(bronping, "PINGS", pings)

    assert bronping.main(["--alleen", "cbs"]) == 0
    assert "rio-b" not in capsys.readouterr().out


def test_een_onbekende_bron_is_een_gebruiksfout():
    assert bronping.main(["--alleen", "uwv"]) == 2


# --- de pipeline ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text())


def _regels(job: dict) -> list[dict]:
    return [r for r in job.get("rules") or [] if isinstance(r, dict)]


def test_de_ping_draait_alleen_gepland_of_met_de_hand_met_de_variabele(ci):
    job = ci["bron:ping"]
    voorwaarden = [r["if"] for r in _regels(job)]
    assert voorwaarden, "bron:ping heeft rules nodig"
    for voorwaarde in voorwaarden:
        assert "$BRON_PING" in voorwaarde
        assert '$CI_PIPELINE_SOURCE == "schedule"' in voorwaarde or '$CI_PIPELINE_SOURCE == "web"' in voorwaarde
    assert "scripts/bronping.py" in " ".join(job["script"])
    assert job.get("allow_failure") is not True  # een rode ping is het signaal


def test_geen_andere_job_draait_in_een_geplande_pipeline(ci):
    """Een schedule op main mag niets bouwen of uitrollen: alleen de ping (en de evals met EVAL_BASE_URL)."""
    for naam, job in ci.items():
        if naam in ("workflow", "bron:ping", "eval:bronwaarheid") or not isinstance(job, dict) or "rules" not in job:
            continue
        regels = _regels(job)
        sluit_uit = any(
            r.get("when") == "never" and '$CI_PIPELINE_SOURCE == "schedule"' in r.get("if", "") for r in regels
        )
        for r in regels:
            voorwaarde = r.get("if", "")
            if "$CI_DEFAULT_BRANCH" in voorwaarde and "schedule" not in voorwaarde and not sluit_uit:
                pytest.fail(f"{naam}: de regel op main sluit een geplande pipeline niet uit: {voorwaarde}")
            if r.get("when") in ("on_failure", "always") and "if" not in r and not sluit_uit:
                pytest.fail(f"{naam}: '{r['when']}' zonder voorwaarde draait ook in een geplande pipeline")

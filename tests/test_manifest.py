"""Manifest per antwoord en rapport (#345): herkomst, geen inhoud."""

from unittest.mock import patch

import pandas as pd

from agent import manifest
from core.config import SEED, TEMPERATURE
from tools import store

_VASTE_SLEUTELS = {"model", "model_naam", "sampling", "prompt_hash", "catalogus", "app", "data_as_of", "gemaakt_op"}


def test_provider_zonder_seed_staat_in_het_manifest():
    with patch("agent.manifest.get_supported_openai_params", return_value=["temperature", "max_tokens"]):
        m = manifest.bouw("openai/gpt-oss", [])
    assert m["sampling"] == {
        "seed": SEED,
        "seed_toegepast": False,
        "temperature": TEMPERATURE,
        "temperature_toegepast": True,
    }


def test_provider_met_seed_staat_in_het_manifest():
    with patch("agent.manifest.get_supported_openai_params", return_value=["temperature", "seed"]):
        m = manifest.bouw("anthropic/claude", [])
    assert m["sampling"]["seed_toegepast"] is True


def test_onbekende_ondersteuning_is_onbekend_niet_toegepast():
    """Bronuitval bij de capability-lookup is geen feit over het antwoord: None, geen gok."""
    with patch("agent.manifest.get_supported_openai_params", side_effect=RuntimeError("?")):
        m = manifest.bouw("x/y", [])
    assert m["sampling"]["seed_toegepast"] is None
    assert m["sampling"]["temperature_toegepast"] is None


def _bouw(keys):
    with patch("agent.manifest.get_supported_openai_params", return_value=[]):
        return manifest.bouw("m/x", keys)


def test_data_as_of_per_dataset_met_periodestatus_en_update():
    store.put(
        "cbs:fx",
        pd.DataFrame({"Perioden": ["2023SJ00", "2024SJ00"], "Periodestatus": ["Definitief", "Voorlopig"]}),
        store.KeyMeta(bron="cbs", dataset="fx", periodekolom="Perioden"),
    )
    with patch("agent.manifest.catalogus_laatste_update", return_value="2026-09-15"):
        m = _bouw(["cbs:fx"])
    [entry] = m["data_as_of"]
    assert entry["bron"] == "cbs" and entry["dataset"] == "fx"
    assert entry["laatste_update"] == "2026-09-15"
    assert entry["periodestatus"] == ["Definitief", "Voorlopig"]


def test_afgeleide_keys_tellen_als_een_dataset():
    store.put("duo:fx:1", pd.DataFrame({"AANTAL": [1]}), store.KeyMeta(bron="duo", dataset="fx", resource=1))
    store.derive("duo:fx:1", "duo:fx:1:abc", pd.DataFrame({"AANTAL": [1]}))
    m = _bouw(["duo:fx:1", "duo:fx:1:abc"])
    assert len(m["data_as_of"]) == 1


def test_herladen_op_reist_mee():
    store.put("duo:fx:1", pd.DataFrame({"AANTAL": [1]}), store.KeyMeta(bron="duo", dataset="fx", resource=1))
    store.markeer_herladen("duo:fx:1", "11-10-2026")
    m = _bouw(["duo:fx:1"])
    assert m["data_as_of"][0]["herladen_op"] == "11-10-2026"


def test_onbekende_key_valt_stil_weg():
    m = _bouw(["bestaat:niet"])
    assert m["data_as_of"] == []


def test_manifest_draagt_alleen_herkomst_geen_inhoud():
    """Vaste sleutels, geen vraag- of antwoordtekst en geen gebruikersvelden (privacy-criterium #345)."""
    m = _bouw([])
    assert set(m) == _VASTE_SLEUTELS
    assert m["prompt_hash"] and len(m["prompt_hash"]) == 12
    assert m["catalogus"] and len(m["catalogus"]) == 12
    assert m["app"]


def test_providerversie_komt_erbij_als_hij_afwijkt():
    with patch("agent.manifest.get_supported_openai_params", return_value=[]):
        met = manifest.bouw("anthropic/claude", [], model_versie="claude-4-6-20250929")
        zonder = manifest.bouw("anthropic/claude", [], model_versie="anthropic/claude")
    assert met["model_versie"] == "claude-4-6-20250929"
    assert "model_versie" not in zonder


def test_slotbericht_draagt_het_manifest():
    from agent.loop import LoopResult
    from agent.run import _slotbericht

    event = _slotbericht("Antwoord.", LoopResult(), [], False, [], manifest={"model": "m/x"})
    assert event["manifest"] == {"model": "m/x"}


def test_manifest_draagt_de_modelnaam_naast_het_id():
    """De gebruikersnaam voor de Verantwoording (BEV-10); het id blijft voor herhaalbaarheid."""
    with patch("agent.manifest.get_supported_openai_params", return_value=[]):
        bekend = manifest.bouw("azure_ai/claude-sonnet-5-5", [])
        onbekend = manifest.bouw("azure_ai/nieuw-model", [])
    assert (bekend["model"], bekend["model_naam"]) == ("azure_ai/claude-sonnet-5-5", "Claude Sonnet 5.5")
    assert (onbekend["model"], onbekend["model_naam"]) == ("azure_ai/nieuw-model", "nieuw-model")

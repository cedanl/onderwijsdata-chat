"""De uitkomst van search_catalog lezen in tests: altijd de vaste envelope (#358, stap 2)."""

import json

STATUSSEN = frozenset(
    {
        "candidates",
        "no_match",
        "needs_clarification",
        "out_of_scope",
        "metadata_unknown",
        "source_unavailable",
        "tool_error",
    }
)


def envelop(uitkomst: str) -> dict:
    """De envelope van een zoekuitkomst; faalt als het geen geldige envelope is."""
    envelop_ = json.loads(uitkomst)
    assert isinstance(envelop_, dict), f"geen envelope: {uitkomst[:120]}"
    assert envelop_["status"] in STATUSSEN, envelop_["status"]
    assert envelop_["catalogus"]
    return envelop_


def treffers(uitkomst: str) -> list[dict]:
    """De kandidaten van een zoekuitkomst; leeg als er geen zijn."""
    return envelop(uitkomst).get("kandidaten", [])


def meldingen(uitkomst: str) -> list[str]:
    """Alle meldingen van een zoekuitkomst: `melding` eerst, dan `meldingen`."""
    envelop_ = envelop(uitkomst)
    return [*([envelop_["melding"]] if "melding" in envelop_ else []), *envelop_.get("meldingen", [])]

"""Which cached datasets belong to one conversation.

The store is shared by every session, so reports and dashboards must ask the
session which of its keys are theirs instead of listing the whole store.
"""

import json
from dataclasses import dataclass, field

from tools import fouten, herlaad, store
from tools.schemas import TOOL_COMPUTE_KPI, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS

from . import recepten

# Rekentools waarvan de uitkomst in de chat al uit de data kwam: bewijs voor het rapport (#397).
# query_data alleen met aggregatie: een rijenselectie staat al in de datasetcontext.
_REKENTOOLS = frozenset({TOOL_COMPUTE_KPI, TOOL_RUN_ANALYSIS})
_MAX_REKENBEWIJS = 30


def _rekent(call: dict) -> bool:
    if call.get("name") in _REKENTOOLS:
        return True
    return call.get("name") == TOOL_QUERY_DATA and bool((call.get("arguments") or {}).get("aggregate"))


def record_data_key(session: dict, tool_result: str, call: dict | None = None) -> None:
    """Remember the data_key a tool result points to, if it has one.

    `call` ({"name", "arguments"}) is the tool call that produced it: its
    provenance. A report needs that to reuse the selection the conversation
    made instead of guessing it again from the key (#174).
    """
    try:
        parsed = json.loads(tool_result)
    except (TypeError, ValueError):
        return
    key = parsed.get("data_key") if isinstance(parsed, dict) else None
    if isinstance(key, str):
        keys = session.setdefault("data_keys", [])
        if key not in keys:
            keys.append(key)
        if call is not None:
            # Keys are deterministic per selection: the first producer is the real one.
            session.setdefault("data_provenance", {}).setdefault(key, call)
            # Dit antwoord rust op de data zoals ze nu is: voor deze sessie is ze niet herladen (#472).
            store.markeer_herladen(key, None)
            # Buiten het geheugen bewaard bij het opslaan van het gesprek: zo overleeft de key een herstart (#472).
            if session.get("username") and (recept := herlaad.recept(key, call)) is not None:
                recepten.onthoud(session["username"], key, recept)


def data_lineage(session: dict, key: str) -> list[dict]:
    """The tool calls that produced `key`, from the load call to the last query.

    A query_data call names its parent in its data_key argument; follow that
    back as far as provenance was recorded. Empty when nothing was recorded.
    """
    provenance = session.get("data_provenance", {})
    lineage: list[dict] = []
    while key in provenance and len(lineage) < len(provenance):
        call = provenance[key]
        lineage.insert(0, call)
        key = call.get("arguments", {}).get("data_key")
    return lineage


# De store leeft in het geheugen: na een herstart is de data van een gesprek weg (CH-44).
_OPNIEUW = "Stel je vraag opnieuw om de data op te halen; daarna kun je het rapport maken."
DATA_WEG = f"De data van dit gesprek is niet meer beschikbaar: de server is intussen herstart. {_OPNIEUW}"


def session_data_keys(session: dict) -> list[str]:
    """This conversation's data keys that are still in the store, in load order."""
    return [key for key in session.get("data_keys", []) if store.get(key) is not None]


def ontbrekende_data_keys(session: dict) -> list[str]:
    """Keys this conversation loaded that the store no longer holds."""
    return [key for key in session.get("data_keys", []) if store.get(key) is None]


@dataclass(frozen=True)
class Herstel:
    """Wat herstel_data_keys terugzette en wat niet."""

    # Per herladen key van het gesprek de melding dat de bron kan zijn gewijzigd.
    notities: tuple[str, ...] = ()
    # Key -> waarom hij niet terugkwam; leeg als er geen recept van was.
    onherstelbaar: dict[str, str] = field(default_factory=dict)

    @property
    def melding(self) -> str:
        """Per key de stap of bron die het tegenhield; zonder recept de melding van vóór #472."""
        redenen = list(dict.fromkeys(r for r in self.onherstelbaar.values() if r))
        if not redenen:
            return DATA_WEG
        return f"De data van dit gesprek is niet meer beschikbaar. {' '.join(redenen)} {_OPNIEUW}"

    @property
    def notitie(self) -> str | None:
        """De melding bij herladen data, of None als het gesprek alleen data van zijn eigen antwoorden heeft."""
        # De langste noemt ook wanneer een CBS-tabel laatst wijzigde.
        return f"De data van dit gesprek is {max(self.notities, key=len)}." if self.notities else None


def herstel_data_keys(session: dict, username: str | None) -> Herstel:
    """Haal de keys van dit gesprek die de store kwijt is terug uit hun recept (#472).

    Wat niet terugkomt, staat met zijn reden in `onherstelbaar`: wie daarop doorgaat,
    werkt op een deel van de data. De melding komt van elke key die na zijn antwoord is
    opgehaald, ook door een eerder verzoek of de vraag van een ander.
    """
    onherstelbaar: dict[str, str] = {}
    for key in session.get("data_keys", []):
        if store.get(key) is not None:
            recepten.markeer_na_herstart(username, key)  # er nog, of al terug als ouder van een eerdere key
            continue
        uitkomst = recepten.terughalen(username, key)
        if uitkomst is None:
            onherstelbaar[key] = ""
        elif not uitkomst.gelukt:
            onherstelbaar[key] = uitkomst.melding
    notities = (tekst for key in session_data_keys(session) if (tekst := herlaad.notitie(key)))
    return Herstel(tuple(dict.fromkeys(notities)), onherstelbaar)


def record_rekenbewijs(session: dict, tool_result: str, call: dict) -> None:
    """Bewaar de uitkomst van een geslaagde rekentool met zijn aanroep (#397).

    Een KPI of afgeleid getal (som, verschil) dat compute_kpi of run_analysis gaf, is in de
    rapportfase anders geen bewijs: die controleert alleen zijn eigen toolresultaten.
    Alleen het toolresultaat telt, nooit de vrije antwoordtekst.
    """
    if not _rekent(call) or fouten.code(tool_result) is not None:
        return
    try:
        parsed = json.loads(tool_result)
    except (TypeError, ValueError):
        return
    if not isinstance(parsed, dict) or "fout" in parsed:
        return
    bewijs = session.setdefault("rekenbewijs", [])
    bewijs.append({"tool": call["name"], "argumenten": call.get("arguments") or {}, "resultaat": tool_result})
    del bewijs[:-_MAX_REKENBEWIJS]


def rekenbewijs(session: dict) -> list[dict]:
    """De bewaarde rekenuitkomsten van dit gesprek, oudste eerst."""
    return list(session.get("rekenbewijs") or [])

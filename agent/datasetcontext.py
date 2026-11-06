"""Wat een rapport van de data van een gesprek weet: de datasets, hun herlaadrecept en hun bronregels.

Stond in agent/dashboard.py, dat het met de rapportgenerator deelde; de dashboardbouwer is weg (#765).
"""

from __future__ import annotations

import asyncio
import json

from agent.session_data import (
    DATA_WEG,
    data_lineage,
    gebruikersvragen,
    herstel_data_keys,
    ontbrekende_data_keys,
    session_data_keys,
)
from agent.stream import Emit
from core.errors import Gebruikersfout
from tools import arbeidsmarkt, financien, store, studiekeuze, wo_personeel
from tools.catalog import bron_titel, resource_titel
from tools.columns import sample_values
from tools.schemas import (
    TOOL_GET_BESTUURSFINANCIEN,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_GET_ROA_BENCHMARK,
    TOOL_GET_STUDIEKEUZE,
    TOOL_GET_UWV_VACATURES,
    TOOL_GET_WO_PERSONEEL,
)

# De tools die data laden: alleen hun aanroep gaat als herlaadaanroep het recept in (#505).
# De arbeidsmarkttools laden sinds #577 ook een dataset, de financiën en WOPI sinds #956.
LAADTOOLS = frozenset(
    {
        TOOL_GET_DUO_DATA,
        TOOL_GET_CBS_DATA,
        TOOL_GET_RIO_DATA,
        TOOL_GET_UWV_VACATURES,
        TOOL_GET_ROA_BENCHMARK,
        TOOL_GET_BESTUURSFINANCIEN,
        TOOL_GET_WO_PERSONEEL,
        TOOL_GET_STUDIEKEUZE,
    }
)
# De vaste dataset achter een tool waarvan de aanroep geen dataset-ID noemt (#577, #956).
_VASTE_DATASET = {
    **arbeidsmarkt.DATASET,
    TOOL_GET_BESTUURSFINANCIEN: financien.DATASET,
    TOOL_GET_WO_PERSONEEL: wo_personeel.DATASET,
    TOOL_GET_STUDIEKEUZE: studiekeuze.DATASET,
}


def build_recipe(datasets: list[dict]) -> list[dict]:
    """Reload calls for the given datasets, one per load call.

    The recorded load call (its herkomst) is used as is, so CBS filters survive
    a reload (#174). Without herkomst the key itself says how to reload. A load that took the vo part of a
    source (#879, #880) says so: the gate of that turn opened it, not the model's arguments.
    """
    recipe: list[dict] = []
    for ds in datasets:
        herkomst = ds.get("herkomst") or []
        if herkomst and herkomst[0]["name"] in LAADTOOLS:
            args = dict(herkomst[0]["arguments"])
            if (known := store.meta(ds["data_key"])) and known.vo_context:
                args["vo_context"] = True
            call = {"name": herkomst[0]["name"], "arguments": json.dumps(args)}
        else:
            call = _reload_call_from_key(ds["data_key"])
        if call and call not in recipe:
            recipe.append(call)
    return recipe


def _reload_call_from_key(key: str) -> dict | None:
    # Derived keys append a selection hash (duo:p01hoinges:3:74a5c5e2); reload the source.
    parts = key.split(":")
    if parts[0] == "duo" and len(parts) >= 3:
        return {
            "name": TOOL_GET_DUO_DATA,
            "arguments": json.dumps({"dataset_id": parts[1], "resource": _try_int(parts[2])}),
        }
    if parts[0] == "cbs" and len(parts) >= 2:
        return {"name": TOOL_GET_CBS_DATA, "arguments": json.dumps({"dataset_id": parts[1]})}
    if parts[0] == "rio" and len(parts) >= 2:
        return {"name": TOOL_GET_RIO_DATA, "arguments": json.dumps({"resource": parts[1]})}
    return None


def _try_int(val: str) -> int | str:
    try:
        return int(val)
    except ValueError:
        return val


def _column_summary(df, col: str, max_examples: int = 5) -> dict:
    return {
        "naam": col,
        "type": str(df[col].dtype),
        "voorbeelden": sample_values(df[col], max_examples),
    }


async def herstel_data(session: dict, emit: Emit) -> None:
    """Haal terug wat een herstart uit de store wiste, vóór build_dataset_context (#472).

    Alleen een heropend gesprek kan keys hebben die de store kwijt is: de keys komen uit de
    recepten die bij het gesprek zijn bewaard. Herladen gaat naar de bron: in een thread, niet
    op de event loop. Herladen data krijgt een melding, want de bron kan intussen zijn gewijzigd.
    """
    herstel = await asyncio.to_thread(herstel_data_keys, session, session.get("username"))
    if herstel.onherstelbaar:
        raise Gebruikersfout(herstel.melding)
    if herstel.notitie:
        await emit({"type": "toast", "message": herstel.notitie, "level": "info"})


def build_dataset_context(session: dict) -> dict:
    """Build a context dict describing the available datasets for the LLM.

    Fail-closed when data this conversation loaded is gone: a report on the rest, or a
    generic 'try again', would not tell the user that the question has to be asked again (CH-44).
    Reloading it is herstel_data's job, before this (#472).
    """
    if ontbrekende_data_keys(session):
        raise Gebruikersfout(DATA_WEG)
    datasets: list[dict] = []
    for key in session_data_keys(session):
        df = store.get(key)
        known = store.meta(key)
        datasets.append(
            {
                "data_key": key,
                "row_count": len(df),
                "columns": [_column_summary(df, col) for col in df.columns],
                "herkomst": data_lineage(session, key),
                # False: one page of the source, not the whole source (#186); the report says so (#578).
                "volledig": known.volledig if known else True,
            }
        )

    settings = session.get("chat_settings") or {}
    instelling = settings.get("instelling", "")

    return {
        "datasets": datasets,
        "instelling": instelling,
        "topic": _eerste_vraag(session),
    }


def _eerste_vraag(session: dict) -> str:
    """De eerste vraag van het gesprek: het onderwerp van het rapport.

    Uit de berichten, niet uit `turns` (#732). Een heropend gesprek (verversen, terug van /rapporten)
    begint met lege `turns`, en een vraag die een verduidelijkingskaart kreeg wordt geen beurt: dan was de
    eerste vraag ná het heropenen, of de gekozen optie, het onderwerp. De berichten bevatten beide.
    """
    if vragen := gebruikersvragen(session):
        return vragen[0]
    turns = session.get("turns") or []
    return turns[0].get("question", "") if turns else ""


_SOURCE_PREFIXES = {
    TOOL_GET_DUO_DATA: "DUO",
    TOOL_GET_CBS_DATA: "CBS",
    TOOL_GET_RIO_DATA: "RIO",
    TOOL_GET_UWV_VACATURES: "UWV",
    TOOL_GET_ROA_BENCHMARK: "ROA",
    TOOL_GET_BESTUURSFINANCIEN: "DUO",
    TOOL_GET_WO_PERSONEEL: "UNL",
    TOOL_GET_STUDIEKEUZE: "LCSK",
}


def _source_label(prefix: str, dataset: str, resource, vo_context: bool = False) -> str:
    """ "CBS — Hoger onderwijs; ingeschrevenen, … (85423NED)": titel uit de catalogus, niet van het model."""
    if not dataset:
        return prefix
    titel = bron_titel(dataset, vo_context=vo_context)
    label = f"{prefix} — {titel} ({dataset})" if titel != dataset else f"{prefix} — {dataset}"
    if prefix == "DUO" and resource is not None and (naam := resource_titel(dataset, resource)):
        label += f", {naam}"
    return label


def sources_from_recipe(recipe: list[dict]) -> list[str]:
    """Bronvermelding voor elke dataset in het recept.

    Altijd uit code: een model schreef bij een juist dataset-ID een verzonnen titel (#196).
    """
    sources: list[str] = []
    for call in recipe:
        prefix = _SOURCE_PREFIXES.get(call.get("name", ""))
        if not prefix:
            continue
        try:
            args = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else call["arguments"]
        except (json.JSONDecodeError, TypeError):
            args = {}
        # Een arbeidsmarkttool, de financiën en WOPI laden één vaste dataset (#577, #956): het ID komt uit de tool.
        dataset = args.get("dataset_id") or args.get("resource") or _VASTE_DATASET.get(call["name"], "")
        resource = args.get("resource") if args.get("dataset_id") else None
        label = _source_label(prefix, dataset, resource, args.get("vo_context") is True)
        if peilmoment := arbeidsmarkt.peilmoment(call["name"]):
            label += f", {peilmoment}"
        if label not in sources:
            sources.append(label)
    return sources

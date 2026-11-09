"""Het schema van de Studiekeuzedatabase in search_catalog en dataset_details (#978).

De export van LCSK beschrijft zichzelf: 45 tabellen en 639 kolommen in `exporttabellen` en `exportkolommen`. Het
pakket bouwt daaruit de schemacatalogus (`onderwijsbronnen.skdb.schema`); deze module zet hem om naar wat het model
ziet. Twee lagen, om de leveringsvoorwaarden (art. 11.1, geen doorlevering):

- zoeken gebruikt alleen de tabelnamen uit de code (`skdb.MOGELIJKHEDEN`, in het catalogusrecord als `tabellen`): een
  hit op "tracks" of "studieadvies" noemt die tabel en wat de chat ermee kan, zonder de export te downloaden;
- dataset_details leest de omschrijvingen, kolommen en types uit de export van vandaag (dezelfde lading als
  get_studiekeuze, `studiekeuze._export`): `skdb:studiekeuzedatabase` geeft het overzicht van de tabellen,
  `skdb:studiekeuzedatabase/<tabel>` het schema van één tabel.

Wat de chat met een tabel kan, staat per tabel: een weergave van get_studiekeuze, alleen in het pakket leesbaar, of
bewust niet in de chat omdat een andere bron leidend is. Zo gaat "niet beschikbaar" over de tool, niet over de bron.
De sleutels naar andere bronnen komen uit `onderwijsbronnen.sleutels` (#958), dezelfde lijst als `relatie` en de
catalogus, niet uit een tweede lijst.
"""

from __future__ import annotations

import json
import logging
import re

from onderwijsbronnen import skdb, sleutels
from onderwijsbronnen.skdb import schemakaart

from .catalog import _DETAILS_BUDGET as DETAILS_BUDGET
from .catalog import koppelbaar_via
from .schemas import TOOL_GET_STUDIEKEUZE

logger = logging.getLogger(__name__)

DATASET_ID = "skdb:studiekeuzedatabase"
_TABEL_ID = re.compile(r"^(?:skdb[:/])?studiekeuzedatabase[/.:](?P<tabel>[A-Za-z]+)$", re.IGNORECASE)
# Een omschrijving van LCSK gaat begrensd naar het model; past een tabel dan nog niet, korter en zo nodig zonder.
_OMSCHRIJVING_MAX = (200, 100, 50, 0)
_OVERZICHT_MAX = 160

_KAN = {
    schemakaart.OVERZICHT: f"in de chat via {TOOL_GET_STUDIEKEUZE}, met de genoemde weergave",
    schemakaart.PAKKET: "alleen in het pakket leesbaar (skdb.load('<tabel>')); de bron heeft de tabel, de chat geen weergave",
    schemakaart.ANDERE_BRON: "bewust niet in de chat, omdat een andere bron leidend is",
}
_LEGENDA = {
    "weergave": _KAN[schemakaart.OVERZICHT],
    "pakket": _KAN[schemakaart.PAKKET],
    "andere_bron": _KAN[schemakaart.ANDERE_BRON],
}
_INSTRUCTIE = (
    "Dit is het schema zoals LCSK het in de export beschrijft. Noem bij een antwoord erover de bronregel; de vermelding "
    "van LCSK is verplicht. Een tabel die alleen in het pakket leesbaar is, heeft de bron wel: zeg dat, geef er geen "
    "cijfers voor, en zeg niet dat de data niet bestaat. Bij een kolom met een andere bron leidend: noem die bron."
)
# Bij elke zoekhit op de Studiekeuzedatabase: anders leest het model alleen "op te vragen met get_studiekeuze".
SCHEMA_HINT = f"Tabellen, kolommen, types en wat de chat ermee kan: dataset_details('{DATASET_ID}')."
_VERVOLGSTAP = (
    "Kolommen, types, korrel, sleutels en relaties van één tabel: dataset_details('skdb:studiekeuzedatabase/<tabel>')."
)


def tabel_uit_id(dataset_id: str) -> str | None:
    """De tabel in `skdb:studiekeuzedatabase/<tabel>` (ook zonder `skdb:`); None voor elk ander ID."""
    gevonden = _TABEL_ID.match(str(dataset_id).strip())
    return gevonden["tabel"].lower() if gevonden else None


def _weergaven(mogelijkheid: schemakaart.Mogelijkheid) -> list[str]:
    from .studiekeuze import WEERGAVEN  # hier: studiekeuze laadt de store, en die deze catalogus

    return [w for w in WEERGAVEN if w in mogelijkheid.overzichten]


def kan(tabel: str) -> str:
    """Wat de chat met deze tabel kan, als zin voor het model."""
    mogelijkheid = schemakaart.mogelijkheid(tabel)
    if mogelijkheid.soort == schemakaart.OVERZICHT:
        return f"in de chat via {TOOL_GET_STUDIEKEUZE} (weergave {', '.join(_weergaven(mogelijkheid))})"
    if mogelijkheid.soort == schemakaart.ANDERE_BRON:
        return f"bewust niet in de chat: {mogelijkheid.andere_bron}"
    return _KAN[schemakaart.PAKKET].replace("<tabel>", tabel)


def _kort(tabel: str) -> str:
    """Wat er kan, kort, voor het overzicht van 45 tabellen (de legenda staat erbij)."""
    mogelijkheid = schemakaart.mogelijkheid(tabel)
    if mogelijkheid.soort == schemakaart.OVERZICHT:
        return f"weergave {', '.join(_weergaven(mogelijkheid))}"
    if mogelijkheid.soort == schemakaart.ANDERE_BRON:
        return f"andere_bron: {mogelijkheid.andere_bron}"
    return "pakket"


def tabelregel(tabel: str) -> str:
    """Een geraakte tabel in een zoekhit: 'tracks: alleen in het pakket leesbaar …'."""
    return f"{tabel}: {kan(tabel)}"


def _export() -> tuple[skdb.Export | None, str | None]:
    """De export van vandaag (de lading van get_studiekeuze), of de reden dat die er nu niet is."""
    from . import studiekeuze  # hier: studiekeuze laadt de store, en die deze catalogus

    try:
        return studiekeuze._export(), None
    except skdb.SkdbFout as e:  # ook GeenSleutel; de melding noemt de sleutel nooit
        reden = str(e)
    except Exception as e:  # netwerk, onverwacht
        logger.warning("skdb-schema export niet beschikbaar: %s", type(e).__name__)
        reden = f"de export is niet op te halen ({type(e).__name__})"
    return None, f"Het schema komt uit de export van vandaag, en die is nu niet beschikbaar: {reden}"


def _afgekapt(tekst: str | None, maximum: int) -> str | None:
    if not tekst or len(tekst) <= maximum:
        return tekst
    return tekst[: maximum - 1].rstrip() + "…"


def _bron(export: skdb.Export) -> dict:
    from .studiekeuze import bronregel  # hier: studiekeuze laadt de store, en die deze catalogus

    return {"bronregel": bronregel(export.herkomst), "instructie": _INSTRUCTIE}


def details(entry: dict, status: dict) -> str:
    """dataset_details van `skdb:studiekeuzedatabase`: de status van het record (via get_studiekeuze) met het
    overzicht van de tabellen uit de export; zonder export de tabelnamen met wat er kan, en de reden."""
    uit: dict = {"bron": entry.get("bron", DATASET_ID), **status, "koppelbaar_via": koppelbaar_via(entry)}
    export, reden = _export()
    if export is None:
        uit["schema"] = {
            "melding": reden,
            "kan": _LEGENDA,
            "tabellen": [{"tabel": t, "kan": _kort(t)} for t in sorted(schemakaart.MOGELIJKHEDEN)],
        }
        return json.dumps({**uit, "vervolgstap": _VERVOLGSTAP}, ensure_ascii=False, separators=(",", ":"))
    schema = skdb.schema(export)
    uit["schema"] = {
        "editie": schema["editie"],
        "null": schema["null"],
        "kan": _LEGENDA,
        "tabellen": [
            {
                "tabel": t["tabel"],
                "omschrijving": _afgekapt(t["omschrijving"], _OVERZICHT_MAX),
                "kolommen": len(t["kolommen"]),
                "kan": _kort(t["tabel"]),
            }
            for t in schema["tabellen"]
        ],
    }
    return json.dumps({**uit, "vervolgstap": _VERVOLGSTAP, **_bron(export)}, ensure_ascii=False, separators=(",", ":"))


def _kolomtekst(kolom: dict, maximum: int) -> str:
    """'number: <omschrijving>', of 'number; andere bron leidend: DUO (…)' voor een kolom die de chat niet toont."""
    if "andere_bron" in kolom:
        return f"{kolom['type']}; andere bron leidend: {kolom['andere_bron']}"
    omschrijving = _afgekapt(kolom.get("omschrijving"), maximum) if maximum else None
    return f"{kolom['type']}: {omschrijving}" if omschrijving else str(kolom["type"])


def _sleutels(kolommen: list[dict]) -> list[dict]:
    """De kolommen die een sleutel naar een andere bron zijn (`onderwijsbronnen.sleutels`); alleen hbo en wo."""
    return sleutels.paren((str(k["kolom"]) for k in kolommen), ["HBO", "WO"])


def _ingekort(maximum: int) -> dict:
    """Wat het model moet weten als de omschrijvingen korter zijn dan in de export, om binnen het budget te passen."""
    if maximum == _OMSCHRIJVING_MAX[0]:
        return {}
    if maximum:
        return {"kolomdetail_weggelaten": f"De omschrijvingen van de kolommen zijn ingekort tot {maximum} tekens."}
    return {"kolomdetail_weggelaten": "Zonder de omschrijvingen van de kolommen; de types staan er wel."}


def _tabel_json(entry: dict, tabel: dict, schema: dict, export: skdb.Export) -> str:
    basis = {
        "bron": entry.get("bron", DATASET_ID),
        "dataset_id": f"{DATASET_ID}/{tabel['tabel']}",
        "tabel": tabel["tabel"],
        "omschrijving": tabel["omschrijving"],
        "kan": kan(tabel["tabel"]),
        "korrel": tabel["korrel"],
        "sleutels": _sleutels(tabel["kolommen"]),
        "relaties": tabel["relaties"],
        "jaarkolommen": tabel["jaarkolommen"],
    }
    rest = {"editie": schema["editie"], "null": schema["null"], **_bron(export)}
    for maximum in _OMSCHRIJVING_MAX:
        kolommen = {k["kolom"]: _kolomtekst(k, maximum) for k in tabel["kolommen"]}
        tekst = json.dumps(
            {**basis, "kolommen": kolommen, **_ingekort(maximum), **rest}, ensure_ascii=False, separators=(",", ":")
        )
        if len(tekst) <= DETAILS_BUDGET:
            break
    return tekst


def tabeldetails(entry: dict, naam: str) -> str:
    """dataset_details van `skdb:studiekeuzedatabase/<tabel>`: het schema van die tabel uit de export."""
    export, reden = _export()
    if export is None:
        if naam not in schemakaart.MOGELIJKHEDEN:
            return _onbekend(naam)
        uit = {"bron": entry.get("bron", DATASET_ID), "tabel": naam, "kan": kan(naam), "melding": reden}
        return json.dumps(uit, ensure_ascii=False, separators=(",", ":"))
    schema = skdb.schema(export)
    tabel = next((t for t in schema["tabellen"] if t["tabel"] == naam), None)
    if tabel is None:
        return _onbekend(naam)
    logger.info("dataset_details id=%s/%s bron=LCSK", DATASET_ID, naam)
    return _tabel_json(entry, tabel, schema, export)


def _onbekend(naam: str) -> str:
    # De naam komt van het model en staat in geen lijst: niet in het log, wel terug naar het model.
    return f"Tabel '{naam}' staat niet in de Studiekeuzedatabase. De tabellen staan in dataset_details('{DATASET_ID}')."

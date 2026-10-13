"""Gesloten selectieschema voor CBS: het model kiest codes, de server bouwt OData (#343).

`get_cbs_data(filters={"$filter": "…"})` liet het model de filtertaal van de bron
schrijven: een implementatiedetail in de interface, en met `$top` besliste het model
zelf of een selectie volledig was. Hier komt een `selectie` binnen — per dimensie een
code (of `*` om uit te splitsen), de periode als lijst of bereik, onderwerpen als
kolomsleutels — en compileert de server de OData-parameters. De rijlimiet is een
beleidsregel (`CBS_ROW_LIMIT`), geen modelparameter.

De volledigheidspoort zit vóór het laden: een selectie waarin een dimensie noch
gepind noch bewust uitgesplitst is, komt niet binnen; de weigering noemt wat
ontbreekt. Periodespelling loopt via tools/periode.py (#342); kolomsleutels toetst
get_cbs_data zelf al (geen tweede controle). Zie ADR-006.

Elke vergelijking gaat als `trim(Dimensie) eq 'code'`: CBS vult de sleutels van een
dimensie op tot één breedte ('4000   ' naast 'T001038') en de feed en get_cbs_dimension
tonen ze gestript, zodat de kale code zonder trim niets matcht (#531).
"""

from . import periode

ALLES = "*"
_SLEUTELS = ("dimensies", "periode", "onderwerpen")
# CBS noemt de tijddimensie vrijwel altijd Perioden; alleen als DataProperties uitvalt
# (geen poort, wel compilatie) wordt op die naam teruggevallen.
_TIJDDIMENSIE_FALLBACK = "Perioden"

_UITLEG = (
    "Geef een selectie met 'dimensies' (per dimensie een code uit get_cbs_dimension, een lijst codes, "
    f"of '{ALLES}' om uit te splitsen), 'periode' (lijst van schooljaren of periodecodes, "
    f"{{'van': …, 'tot': …}}, of '{ALLES}') en optioneel 'onderwerpen' (kolomsleutels)."
)


def _dimensienamen(col_defs: dict) -> tuple[list[str], str | None]:
    """(gewone dimensies, tijddimensie) uit DataProperties."""
    tijd = next((kolom for kolom, d in col_defs.items() if d.get("type") == "TimeDimension"), None)
    dims = [kolom for kolom, d in col_defs.items() if d.get("type", "").endswith("Dimension") and kolom != tijd]
    return dims, tijd


def _code(waarde) -> str:
    """Een dimensiecode als OData-literal: aanhalingstekens verdubbeld."""
    return str(waarde).strip().replace("'", "''")


def _gelijk(dimensie: str, code: str) -> str:
    """Eén vergelijking, op de gestripte sleutel: zie de opgevulde sleutels in de moduledocstring."""
    return f"trim({dimensie}) eq '{code}'"


def _clausule(dimensie: str, waarde) -> str | None:
    """De filterclausule voor één dimensie; None bij `*` (bewust uitsplitsen), '' bij niets."""
    if waarde == ALLES:
        return None
    codes = waarde if isinstance(waarde, list) else [waarde]
    codes = sorted({_code(code) for code in codes if str(code).strip()})
    if not codes:
        return ""
    if len(codes) == 1:
        return _gelijk(dimensie, codes[0])
    return "(" + " or ".join(_gelijk(dimensie, code) for code in codes) + ")"


def _periodecodes(opgave) -> list[str] | str:
    """De CBS-periodecodes van een periodeopgave; een foutmelding als er spelling buiten
    het vocabulaire in zit."""
    if isinstance(opgave, dict):
        van = periode.startjaar_van_spelling(opgave.get("van"))
        tot = periode.startjaar_van_spelling(opgave.get("tot"))
        if van is None or tot is None:
            return (
                f"Periodebereik niet begrepen: {opgave}. Geef 'van' en 'tot' als schooljaar "
                "(bijv. 2020/21), of een lijst periodecodes."
            )
        return [periode.broncode("cbs", jaar) for jaar in range(min(van, tot), max(van, tot) + 1)]
    codes = []
    for waarde in opgave if isinstance(opgave, list) else [opgave]:
        tekst = str(waarde).strip()
        if (jaar := periode.startjaar_van_spelling(tekst)) is not None:
            codes.append(periode.broncode("cbs", jaar))
        elif periode.is_periodecode(tekst):
            codes.append(tekst)
        else:
            return (
                f"Periode '{waarde}' niet begrepen. Geef een schooljaar (2024/25), een CBS-periodecode "
                f"(2024SJ00, 2024JJ00) of '{ALLES}' voor alle periodes."
            )
    if not codes:
        return f"De periode is leeg. Geef een lijst, een bereik of '{ALLES}' voor alle periodes."
    return sorted(set(codes))


def _poort(dataset_id: str, dimensies: dict, heeft_periode: bool, col_defs: dict) -> str | None:
    """De volledigheidspoort: elke dimensie gekozen (code of `*`), de periode benoemd.

    CBS-tabellen bevatten totaalrijen naast hun onderdelen; een dimensie die stilzwijgend
    openblijft, telt later dubbel of maakt rijen ononderscheidbaar (#162). Daarom komt een
    onvolledige selectie niet binnen, vóór er een datacall de deur uitgaat.
    """
    dims, tijd = _dimensienamen(col_defs)
    onbekend = [naam for naam in dimensies if naam not in dims and naam != tijd]
    if onbekend:
        return (
            f"Onbekende dimensie(s) in de selectie voor {dataset_id}: {', '.join(sorted(onbekend))}. "
            f"Deze tabel heeft de dimensies: {', '.join(sorted(dims))}."
        )
    if tijd and tijd in dimensies:
        return f"De tijddimensie {tijd} kies je via 'periode', niet onder 'dimensies'. {_UITLEG}"
    ontbreekt = sorted(naam for naam in dims if naam not in dimensies)
    delen = list(ontbreekt)
    if tijd and not heeft_periode:
        delen.append("de periode ('periode')")
    if not delen:
        return None
    return (
        f"Onvolledige selectie voor {dataset_id}: {', '.join(delen)} niet gekozen. "
        f"Pin elke dimensie op een code (meestal de totaalcode, zie get_cbs_dimension) of "
        f"zet '{ALLES}' om uit te splitsen; kies de periode als lijst, bereik of '{ALLES}'."
    )


def compileer(dataset_id: str, selectie, col_defs: dict | None) -> dict | str:
    """De OData-parameters van een selectie, of de weigering als tekst.

    Zonder DataProperties (bronuitval) is er geen poort maar wel compilatie: bronuitval
    is niet hetzelfde als een onvolledige selectie, en get_cbs_data meldt de ontbrekende
    metadata zelf al.
    """
    if not isinstance(selectie, dict):
        return f"De selectie voor {dataset_id} is geen object. {_UITLEG}"
    if onbekend := sorted(set(selectie) - set(_SLEUTELS)):
        return f"Onbekende sleutel(s) in de selectie: {', '.join(onbekend)}. {_UITLEG}"
    dimensies = selectie.get("dimensies") or {}
    if not isinstance(dimensies, dict):
        return f"'dimensies' moet een object zijn (dimensie → code, lijst of '{ALLES}'). {_UITLEG}"
    heeft_periode = "periode" in selectie

    tijd = _TIJDDIMENSIE_FALLBACK
    if col_defs:
        if fout := _poort(dataset_id, dimensies, heeft_periode, col_defs):
            return fout
        _, tijd = _dimensienamen(col_defs)

    clausules = []
    for naam in sorted(dimensies):
        clausule = _clausule(naam, dimensies[naam])
        if clausule == "":
            return f"Dimensie {naam} heeft geen code. Geef een code uit get_cbs_dimension of '{ALLES}'."
        if clausule:
            clausules.append(clausule)

    if heeft_periode and selectie["periode"] != ALLES and tijd:
        codes = _periodecodes(selectie["periode"])
        if isinstance(codes, str):
            return codes
        if len(codes) == 1:
            clausules.append(_gelijk(tijd, codes[0]))
        else:
            clausules.append("(" + " or ".join(_gelijk(tijd, code) for code in codes) + ")")

    params: dict = {}
    if clausules:
        params["$filter"] = " and ".join(clausules)
    onderwerpen = selectie.get("onderwerpen")
    if onderwerpen:
        if not isinstance(onderwerpen, list):
            return f"'onderwerpen' moet een lijst kolomsleutels zijn. {_UITLEG}"
        params["$select"] = ",".join(str(kolom).strip() for kolom in onderwerpen if str(kolom).strip())
    return params

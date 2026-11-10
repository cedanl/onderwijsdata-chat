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
get_cbs_data zelf al (geen tweede controle). Of de tabel de codes, de periode en de
sector ook kan leveren, vraagt `cbs_preflight` daarna aan het contract (#370). Zie ADR-006.

Elke vergelijking gaat als `trim(Dimensie) eq 'code'`: CBS vult de sleutels van een
dimensie op tot één breedte ('4000   ' naast 'T001038') en de feed en get_cbs_dimension
tonen ze gestript, zodat de kale code zonder trim niets matcht (#531).
"""

from . import periode

ALLES = "*"
SLEUTELS = ("dimensies", "periode", "onderwerpen", "sector")
# De sector waarvoor het model de tabel bevraagt; het contract houdt de codes ertegen (cbs_preflight, #370).
SECTOREN = ("mbo", "hbo", "wo")
# CBS noemt de tijddimensie vrijwel altijd Perioden; alleen als DataProperties uitvalt
# (geen poort, wel compilatie) wordt op die naam teruggevallen.
TIJDDIMENSIE_FALLBACK = "Perioden"

_UITLEG = (
    "Geef een selectie met 'dimensies' (per dimensie een code uit get_cbs_dimension, een lijst codes, "
    f"of '{ALLES}' om uit te splitsen), 'periode' (lijst van schooljaren of periodecodes, "
    f"{{'van': …, 'tot': …}}, of '{ALLES}'), optioneel 'onderwerpen' (kolomsleutels) en optioneel 'sector' "
    "('mbo', 'hbo' of 'wo': de sector waarvoor je de tabel bevraagt)."
)


def dimensienamen(col_defs: dict) -> tuple[list[str], str | None]:
    """(gewone dimensies, tijddimensie) uit DataProperties."""
    tijd = next((kolom for kolom, d in col_defs.items() if d.get("type") == "TimeDimension"), None)
    dims = [kolom for kolom, d in col_defs.items() if d.get("type", "").endswith("Dimension") and kolom != tijd]
    return dims, tijd


def dimensiesleutel(col_defs: dict, naam: str) -> str | None:
    """De API-naam van een dimensie, uit de sleutel of de leesbare titel (hoofdletters en spaties tellen niet).

    dataset_details toont "Geboorteland (ouders)", de bron vraagt `GeboortelandOuders` (#892). Alleen een dimensie,
    de tijddimensie incluis; een onderwerp of een onbekende naam geeft None.
    """
    gezocht = naam.strip().casefold()
    dimensies = {kolom: d for kolom, d in col_defs.items() if d.get("type", "").endswith("Dimension")}
    for kolom in dimensies:
        if kolom.casefold() == gezocht:
            return kolom
    return next(
        (kolom for kolom, d in dimensies.items() if str(d.get("title", "")).strip().casefold() == gezocht), None
    )


def sleutelnamen(col_defs: dict, dimensies: dict) -> dict | str:
    """De dimensies onder hun API-sleutel: de titel of een andere spelling uit dataset_details wordt de sleutel (#1012).

    Een naam die bij geen dimensie hoort, blijft staan: de poort noemt hem dan als onbekend. Twee spellingen van één
    dimensie geven een weigering, niet een stille overschrijving van de ene code door de andere.
    """
    uit: dict = {}
    spellingen: dict[str, list[str]] = {}
    for naam, waarde in dimensies.items():
        sleutel = dimensiesleutel(col_defs, str(naam)) or naam
        spellingen.setdefault(sleutel, []).append(str(naam))
        uit[sleutel] = waarde
    if dubbel := [f"{sleutel} ({', '.join(namen)})" for sleutel, namen in spellingen.items() if len(namen) > 1]:
        return f"Dimensie(s) meer dan eens in de selectie: {'; '.join(dubbel)}. Geef elke dimensie één keer."
    return uit


def met_sleutels(selectie: dict, col_defs: dict | None) -> dict | str:
    """De selectie met elke dimensie onder haar API-sleutel (zie `sleutelnamen`), of de weigering als tekst.

    Zonder DataProperties of zonder dimensie-object blijft de selectie zoals ze is: compileer weigert dat laatste zelf.
    """
    dimensies = selectie.get("dimensies")
    if not col_defs or not isinstance(dimensies, dict):
        return selectie
    met_sleutel = sleutelnamen(col_defs, dimensies)
    return met_sleutel if isinstance(met_sleutel, str) else {**selectie, "dimensies": met_sleutel}


def _met_titel(col_defs: dict, kolom: str) -> str:
    """`sleutel (titel)` als de titel iets anders zegt dan de sleutel, anders de sleutel."""
    titel = str(col_defs.get(kolom, {}).get("title", "")).strip()
    return f"{kolom} ({titel})" if titel and titel != kolom else kolom


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


def periodecodes(opgave) -> list[str] | str:
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
    dims, tijd = dimensienamen(col_defs)
    onbekend = [naam for naam in dimensies if naam not in dims and naam != tijd]
    if onbekend:
        return (
            f"Onbekende dimensie(s) in de selectie voor {dataset_id}: {', '.join(sorted(onbekend))}. "
            f"Deze tabel heeft de dimensies: {', '.join(_met_titel(col_defs, naam) for naam in sorted(dims))}."
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
    if onbekend := sorted(set(selectie) - set(SLEUTELS)):
        return f"Onbekende sleutel(s) in de selectie: {', '.join(onbekend)}. {_UITLEG}"
    if (sector := selectie.get("sector")) is not None and sector not in SECTOREN:
        return f"'sector' is 'mbo', 'hbo' of 'wo', niet {sector!r}. {_UITLEG}"
    dimensies = selectie.get("dimensies") or {}
    if not isinstance(dimensies, dict):
        return f"'dimensies' moet een object zijn (dimensie → code, lijst of '{ALLES}'). {_UITLEG}"
    heeft_periode = "periode" in selectie

    tijd = TIJDDIMENSIE_FALLBACK
    if col_defs:
        dimensies = sleutelnamen(col_defs, dimensies)
        if isinstance(dimensies, str):
            return dimensies
        if fout := _poort(dataset_id, dimensies, heeft_periode, col_defs):
            return fout
        _, tijd = dimensienamen(col_defs)

    clausules = []
    for naam in sorted(dimensies):
        clausule = _clausule(naam, dimensies[naam])
        if clausule == "":
            return f"Dimensie {naam} heeft geen code. Geef een code uit get_cbs_dimension of '{ALLES}'."
        if clausule:
            clausules.append(clausule)

    if heeft_periode and selectie["periode"] != ALLES and tijd:
        codes = periodecodes(selectie["periode"])
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

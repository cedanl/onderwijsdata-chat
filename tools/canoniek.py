"""Canonieke selectie: één identiteit per gelijkwaardige toolaanroep (#342).

`ToolCall.key` was de letterlijke modeljson en elke data_key een hash over de ruwe
argumenten: dezelfde selectie in een andere spelling (sleutelvolgorde, `GESLACHT__in`
met één waarde, `2024/'25` naast `2024SJ00`, `cbs_85353NED` naast `cbs:85353NED`)
kreeg een eigen cache-entry, een eigen load en een eigen snippet. Hier wordt een
aanroep eerst teruggebracht tot zijn canonieke plan; de digest daarvan is de identiteit.

De regel: twee aanroepen krijgen alleen dezelfde digest als ze aantoonbaar hetzelfde
uitvoeren. Periodespelling loopt via tools/periode.py en telt alleen op kolommen die in
elk geladen bestand een periodekolom zijn; `herstel_perioden` herschrijft diezelfde
spellingen vóór het filteren naar de waarde die in de data staat, zodat digest-gelijkheid
en uitvoerings-gelijkheid samenvallen. Wat buiten het vocabulaire valt, wordt niet
gerepareerd maar geweigerd, met de toegestane waarden erbij.
"""

import contextlib
import hashlib
import json
import re

from core.config import CBS_ROW_LIMIT, DUO_ROW_LIMIT

from . import periode

# Kolommen die in elk bestand dat deze app laadt een periodekolom zijn. Alleen hier telt
# een schooljaarspelling als dezelfde selectie, en alleen hier wordt ze gerepareerd. JAAR
# en DIPLOMAJAAR horen er bewust niet bij: een kaal jaartal is geen schooljaar (CH-41).
PERIODEKOLOMMEN = frozenset({"STUDIEJAAR", "STUDIEJAAR_LABEL", "Perioden", "Perioden_label"})

_PREFIX = re.compile(r"^(cbs|duo|rio)[_/:]", re.IGNORECASE)
_STARTJAAR_KAAL = re.compile(r"^20\d{2}$")
_QUOTED = re.compile(r"'[^']*'")
_VERGELIJKENDE_OPS = frozenset({"eq", "in"})
_GRENS_OPS = frozenset({"gte", "lte"})
_MAX_TOEGESTANE_WAARDEN = 15


def parse_filter_key(key: str) -> tuple[str, str]:
    """'KOLOM__op' → (kolom, op); zonder suffix is de operator eq."""
    if "__" in key:
        kolom, op = key.rsplit("__", 1)
    else:
        kolom, op = key, "eq"
    return kolom, op


def sleutel(key: str) -> str:
    """De canonieke spelling van een data_key, voor identiteit: cbs_85353NED,
    CBS:85353ned en cbs:85353NED zijn dezelfde key."""
    return _PREFIX.sub(lambda m: f"{m.group(1).lower()}:", key.strip()).lower()


_CBS_PREFIX = re.compile(r"^cbs[_/:]", re.IGNORECASE)


def zonder_cbs_prefix(dataset_id: str) -> str:
    """Het ID zonder het contract-voorvoegsel van de CBS-package: `cbs:85423NED` → `85423NED` (#370).

    Alleen het voorvoegsel; de spelling van het ID zelf kent de catalogus (`catalog.cbs_bron_id`):
    CBS schrijft `85423NED` naast `80040ned`, dus hoofdletters zijn niet te raden.
    """
    return _CBS_PREFIX.sub("", str(dataset_id).strip())


def _startjaar(kolom: str, waarde) -> int | None:
    """Het startjaar dat `waarde` op deze periodekolom spelt; None als dat er niet uit volgt.

    Op STUDIEJAAR is een kaal jaartal de broncode zelf; op Perioden kan 2024 net zo goed
    2024JJ00 (kalenderjaar) bedoelen en telt alleen een volledige schooljaarspelling.
    """
    if (jaar := periode.startjaar_van_spelling(waarde)) is not None:
        return jaar
    if kolom == "STUDIEJAAR" and _STARTJAAR_KAAL.match(str(waarde).strip()):
        return int(str(waarde).strip())
    return None


def _filterwaarde(kolom: str, waarde) -> str:
    """Eén waarde zoals _apply_filters hem vergelijkt: als tekst, zonder kast."""
    if kolom in PERIODEKOLOMMEN and (jaar := _startjaar(kolom, waarde)) is not None:
        return f"sj:{jaar}"
    return str(waarde).lower()


def _grenswaarde(waarde):
    """gte/lte vergelijkt numeriek waar het kan: '2020' en 2020 zijn dezelfde grens."""
    try:
        return float(waarde)
    except (TypeError, ValueError):
        return str(waarde).lower()


def _canonieke_filters(filters: dict) -> dict:
    """query_data-filters zonder spellingsverschil: eq == in-met-één-waarde, waarden
    kastloos en gesorteerd, twee filters op dezelfde kolom hun doorsnede."""
    canon: dict = {}
    for ruwe_sleutel, waarde in filters.items():
        kolom, op = parse_filter_key(ruwe_sleutel)
        if op in _VERGELIJKENDE_OPS:
            waarden = {_filterwaarde(kolom, w) for w in (waarde if isinstance(waarde, list) else [waarde])}
            canon[kolom] = sorted(waarden & set(canon[kolom])) if kolom in canon else sorted(waarden)
        elif op in _GRENS_OPS:
            canon[f"{kolom}__{op}"] = _grenswaarde(waarde)
        else:
            canon[ruwe_sleutel] = waarde  # onbekende operator: de tool weigert hem, de identiteit blijft letterlijk
    return canon


def _odata_filter(expressie: str) -> str:
    """Witruimte buiten stringliterals samenvouwen: 'Perioden  eq' en 'Perioden eq' zijn
    dezelfde OData-expressie; binnen aanhalingstekens betekent elke spatie iets."""
    delen: list[str] = []
    vorige = 0
    for literal in _QUOTED.finditer(expressie):
        delen += [re.sub(r"\s+", " ", expressie[vorige : literal.start()]), literal.group(0)]
        vorige = literal.end()
    delen.append(re.sub(r"\s+", " ", expressie[vorige:]))
    return "".join(delen).strip()


def _odata_params(filters: dict) -> dict:
    """CBS-laadparameters zonder spellingsverschil; een $top gelijk aan de default valt weg,
    want get_cbs_data zet hem zelf als hij ontbreekt."""
    canon = {}
    for naam, waarde in filters.items():
        if naam == "$top":
            with contextlib.suppress(TypeError, ValueError):
                waarde = int(waarde)
            if waarde == CBS_ROW_LIMIT:
                continue
        elif naam == "$filter" and isinstance(waarde, str):
            waarde = _odata_filter(waarde)
        elif naam == "$select" and isinstance(waarde, str):
            waarde = ",".join(kolom.strip() for kolom in waarde.split(",") if kolom.strip())
        canon[naam] = waarde
    return canon


def _selectiewaarde(waarde) -> str:
    """Eén waarde uit een gesloten selectie (#343), zoals de compiler hem leest."""
    tekst = str(waarde).strip()
    if (jaar := periode.startjaar_van_spelling(tekst)) is not None:
        return f"sj:{jaar}"
    return tekst


def _canonieke_selectie(selectie: dict) -> dict:
    """De gesloten selectie van get_cbs_data (#343) zonder spellingsverschil.

    Alleen equivalenties die de compiler (tools/cbs_selectie.py) zelf ook maakt:
    codelijsten gesorteerd en ontdubbeld, periodespelling als startjaar, een
    van/tot-bereik volgorde-ongevoelig. Wat niet te normaliseren valt, blijft letterlijk.
    """
    canon: dict = {}
    for naam, waarde in selectie.items():
        if naam == "dimensies" and isinstance(waarde, dict):
            canon[naam] = {
                dim: keus
                if keus == "*"  # bewust uitsplitsen (cbs_selectie.ALLES)
                else sorted({_selectiewaarde(w) for w in (keus if isinstance(keus, list) else [keus])})
                for dim, keus in waarde.items()
            }
        elif naam == "periode" and isinstance(waarde, dict) and set(waarde) == {"van", "tot"}:
            grenzen = sorted(_selectiewaarde(waarde[grens]) for grens in ("van", "tot"))
            canon[naam] = {"van": grenzen[0], "tot": grenzen[1]}
        elif naam == "periode" and isinstance(waarde, list | str | int) and waarde != "*":
            canon[naam] = sorted({_selectiewaarde(w) for w in (waarde if isinstance(waarde, list) else [waarde])})
        else:
            canon[naam] = waarde
    return canon


def _leeg(waarde) -> bool:
    return waarde is None or (isinstance(waarde, dict | list | str) and len(waarde) == 0)


def plan(name: str, args: dict) -> dict:
    """Het canonieke plan van een toolaanroep: wat er na normalisatie van de argumenten
    overblijft. Lege en default-argumenten vallen weg; wat niet te normaliseren valt,
    blijft letterlijk staan."""
    canon: dict = {}
    for naam, waarde in args.items():
        if _leeg(waarde):
            continue
        if naam == "data_key" and isinstance(waarde, str):
            canon[naam] = sleutel(waarde)
        elif naam == "filters" and isinstance(waarde, dict) and name == "query_data":
            canon[naam] = _canonieke_filters(waarde)
        elif naam == "filters" and isinstance(waarde, dict) and name == "get_cbs_data":
            if genormaliseerd := _odata_params(waarde):
                canon[naam] = genormaliseerd
        elif naam == "selectie" and isinstance(waarde, dict) and name == "get_cbs_data":
            canon[naam] = _canonieke_selectie(waarde)
        elif naam == "max_rows" and name == "query_data" and waarde == DUO_ROW_LIMIT:
            continue
        else:
            canon[naam] = waarde
    return canon


def digest_plan(canon: dict) -> str:
    """Acht hex-tekens die een canoniek plan identificeren."""
    vorm = json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(vorm.encode()).hexdigest()[:8]


def digest(name: str, args: dict) -> str:
    return digest_plan(plan(name, args))


def aanroep(name: str, args: dict) -> str:
    """De identiteit van een toolaanroep voor cache en dedupe: tool plus plan-digest."""
    return f"{name}:{digest(name, args)}"


def selectie_digest(filters, columns, group_by, aggregate) -> str:
    """De digest van een query_data-selectie, voor de afgeleide data_key."""
    return digest("query_data", {"filters": filters, "columns": columns, "group_by": group_by, "aggregate": aggregate})


def cbs_digest(filters: dict | None) -> str | None:
    """De digest van CBS-laadfilters; None als ze na normalisatie niets selecteren."""
    canon = _odata_params(filters or {})
    return digest_plan(canon) if canon else None


# --- keys van vóór de canonieke digest ------------------------------------------------
# Bewaarde recepten, dashboards en exports verwijzen naar keys uit de oude afleiding
# (md5 over de ruwe argumenten). De laders registreren die als alias (store.alias),
# zodat herladen en verversen blijven werken. Weg te halen zodra er geen opgeslagen
# gesprekken van vóór #342 meer zijn.


def legacy_cbs_key(dataset_id: str, filters: dict | None) -> str | None:
    if not filters:
        return None
    oud = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:8]
    return f"cbs:{dataset_id}:{oud}"


def legacy_selectie_key(data_key: str, filters, columns, group_by, aggregate) -> str:
    sig = json.dumps({"f": filters, "c": columns, "g": group_by, "a": aggregate}, sort_keys=True, default=str)
    return f"{data_key}:{hashlib.md5(sig.encode()).hexdigest()[:8]}"


# --- herstel vóór het filteren --------------------------------------------------------


def _toegestane_waarden(serie) -> str:
    waarden = sorted({str(waarde) for waarde in serie.dropna().unique()})
    getoond = ", ".join(waarden[:_MAX_TOEGESTANE_WAARDEN])
    return getoond + (", …" if len(waarden) > _MAX_TOEGESTANE_WAARDEN else "")


def herstel_perioden(filters: dict, df, periodekolom: str | None, volledig: bool) -> tuple[dict, str | None]:
    """Herschrijf schooljaarspellingen naar de waarde die in de data staat, vóór het filteren.

    2024/'25, 2024/25, 2024-2025 en 2024SJ00 zijn hetzelfde schooljaar; welke spelling de
    kolom gebruikt, bepaalt de data. Een schooljaar dat niet in een volledige selectie
    staat, valt buiten het vocabulaire: dan (filters, weigering) met de waarden die er wél
    staan. Op een afgekapte pagina wordt niet geweigerd: afwezig in de pagina is niet
    afwezig in de bron, dat legt de 0-rijenmelding uit.
    """
    kolommen = set(PERIODEKOLOMMEN)
    if periodekolom:
        kolommen |= {periodekolom, f"{periodekolom}_label"}
    hersteld = {}
    for ruwe_sleutel, waarde in filters.items():
        kolom, op = parse_filter_key(ruwe_sleutel)
        if kolom not in kolommen or op not in _VERGELIJKENDE_OPS or kolom not in df.columns:
            hersteld[ruwe_sleutel] = waarde
            continue
        aanwezig: dict[int, object] = {}  # startjaar → de spelling die deze kolom gebruikt
        bestaand = set()
        for waarde_in_data in df[kolom].dropna().unique():
            bestaand.add(str(waarde_in_data).lower())
            if (jaar := _startjaar(kolom, waarde_in_data)) is not None:
                aanwezig.setdefault(jaar, waarde_in_data)
        nieuw = []
        for gevraagd in waarde if isinstance(waarde, list) else [waarde]:
            jaar = _startjaar(kolom, gevraagd)
            if jaar is None or str(gevraagd).lower() in bestaand:
                nieuw.append(gevraagd)
            elif jaar in aanwezig:
                nieuw.append(aanwezig[jaar])
            elif volledig:
                melding = (
                    f"Periode '{gevraagd}' staat niet in deze data (kolom {kolom}). "
                    f"Toegestane waarden: {_toegestane_waarden(df[kolom])}."
                )
                return filters, melding
            else:
                nieuw.append(gevraagd)
        hersteld[ruwe_sleutel] = nieuw if isinstance(waarde, list) else nieuw[0]
    return hersteld, None

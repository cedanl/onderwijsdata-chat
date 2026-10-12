"""Spellingsvarianten van dezelfde toolaanroep, voor de plan-invariantietest (#347).

De generator produceert alleen varianten waarvan tools/canoniek.py garandeert dat ze
hetzelfde uitvoeren: sleutelvolgorde, `__eq`/`__in`-vormen, waardenkast op gewone
kolommen, lijstvolgorde en -dubbelen, periodespelling op periodekolommen,
data_key-spelling, OData-spatiëring buiten literals en de default `$top`/`max_rows`.
Elke variant hoort op dezelfde plan-digest uit te komen; de test telt de unieke digests.
"""

import random
import re

from core.config import CBS_ROW_LIMIT, DUO_ROW_LIMIT
from tools import periode
from tools.canoniek import PERIODEKOLOMMEN, parse_filter_key

_LITERAL = re.compile(r"'[^']*'")


def _schud(rng: random.Random, mapping: dict) -> dict:
    items = list(mapping.items())
    rng.shuffle(items)
    return dict(items)


def _periodespelling(rng: random.Random, waarde, kolom: str):
    """Een willekeurige gelijkwaardige spelling van een schooljaar op een periodekolom."""
    jaar = periode.startjaar_van_spelling(waarde)
    if jaar is None and kolom == "STUDIEJAAR" and re.fullmatch(r"20\d{2}", str(waarde).strip()):
        jaar = int(str(waarde).strip())
    if jaar is None:
        return waarde  # geen schooljaar: spelling ongemoeid laten
    kort = (jaar + 1) % 100
    opties: list[int | str] = [
        f"{jaar}/{kort:02d}",
        f"{jaar}/'{kort:02d}",
        f"{jaar}-{jaar + 1}",
        f"{jaar}/{jaar + 1}",
        f"{jaar}SJ00",
    ]
    if kolom == "STUDIEJAAR":
        opties += [jaar, str(jaar)]
    return rng.choice(opties)


def _kast(rng: random.Random, waarde):
    if not isinstance(waarde, str):
        return waarde
    return rng.choice([waarde, waarde.lower(), waarde.upper()])


def _filtervariant(rng: random.Random, filters: dict) -> dict:
    variant: dict = {}
    for ruwe_sleutel, waarde in filters.items():
        kolom, op = parse_filter_key(ruwe_sleutel)
        if op in ("gte", "lte"):
            # een getal en zijn tekstvorm zijn dezelfde grens
            variant[ruwe_sleutel] = rng.choice([waarde, str(waarde)])
            continue
        if op not in ("eq", "in"):
            variant[ruwe_sleutel] = waarde
            continue
        waarden = list(waarde) if isinstance(waarde, list) else [waarde]
        if kolom in PERIODEKOLOMMEN:
            waarden = [_periodespelling(rng, w, kolom) for w in waarden]
        else:
            waarden = [_kast(rng, w) for w in waarden]
        if len(waarden) == 1:
            # eq, expliciete __eq en __in met één waarde zijn dezelfde selectie, als lijst of los
            variant[rng.choice([kolom, f"{kolom}__eq", f"{kolom}__in"])] = rng.choice([waarden, waarden[0]])
        else:
            if rng.random() < 0.5:
                waarden = [*waarden, rng.choice(waarden)]  # dubbelen tellen niet
            rng.shuffle(waarden)
            variant[f"{kolom}__in"] = waarden
    return _schud(rng, variant)


def _sleutelvariant(rng: random.Random, key: str) -> str:
    bron, _, rest = key.partition(":")
    scheiding = rng.choice([":", "_", "/"])
    gespeld = f"{rng.choice([bron, bron.upper(), bron.capitalize()])}{scheiding}{rest}"
    return rng.choice([gespeld, gespeld.upper(), gespeld.lower()])


def _odata_variant(rng: random.Random, filters: dict) -> dict:
    variant: dict = {}
    for naam, waarde in filters.items():
        if naam == "$filter" and isinstance(waarde, str):
            delen: list[str] = []
            vorige = 0
            for literal in _LITERAL.finditer(waarde):
                delen += [
                    re.sub(" ", lambda _m: " " * rng.randint(1, 3), waarde[vorige : literal.start()]),
                    literal.group(0),
                ]
                vorige = literal.end()
            delen.append(re.sub(" ", lambda _m: " " * rng.randint(1, 3), waarde[vorige:]))
            variant[naam] = "".join(delen)
        elif naam == "$select" and isinstance(waarde, str):
            variant[naam] = rng.choice([", ", ","]).join(kolom.strip() for kolom in waarde.split(","))
        else:
            variant[naam] = waarde
    if "$top" not in variant and rng.random() < 0.5:
        variant["$top"] = rng.choice([CBS_ROW_LIMIT, str(CBS_ROW_LIMIT)])  # de default is dezelfde aanroep
    return _schud(rng, variant)


def _selectievariant(rng: random.Random, selectie: dict) -> dict:
    variant: dict = {}
    for naam, waarde in selectie.items():
        if naam == "dimensies" and isinstance(waarde, dict):
            dims = {}
            for dim, keus in waarde.items():
                if keus == "*":
                    dims[dim] = keus
                else:
                    codes = list(keus) if isinstance(keus, list) else [keus]
                    if rng.random() < 0.5:
                        codes = [*codes, rng.choice(codes)]
                    rng.shuffle(codes)
                    dims[dim] = codes if (len(codes) > 1 or rng.random() < 0.5) else codes[0]
            variant[naam] = _schud(rng, dims)
        elif naam == "periode" and isinstance(waarde, dict):
            van, tot = waarde["van"], waarde["tot"]
            if rng.random() < 0.5:
                van, tot = tot, van  # de compiler neemt min/max
            variant[naam] = _schud(
                rng, {"van": _periodespelling(rng, van, "periode"), "tot": _periodespelling(rng, tot, "periode")}
            )
        elif naam == "periode" and waarde != "*":
            codes = list(waarde) if isinstance(waarde, list) else [waarde]
            codes = [_periodespelling(rng, code, "periode") for code in codes]
            rng.shuffle(codes)
            variant[naam] = codes
        else:
            variant[naam] = waarde
    return _schud(rng, variant)


def variant(rng: random.Random, tool: str, args: dict) -> dict:
    """Eén gelijkwaardige spelling van `args` voor `tool`."""
    gespeld: dict = {}
    for naam, waarde in args.items():
        if naam == "data_key" and isinstance(waarde, str):
            gespeld[naam] = _sleutelvariant(rng, waarde)
        elif naam == "filters" and tool == "query_data" and isinstance(waarde, dict):
            gespeld[naam] = _filtervariant(rng, waarde)
        elif naam == "filters" and tool == "get_cbs_data" and isinstance(waarde, dict):
            gespeld[naam] = _odata_variant(rng, waarde)
        elif naam == "selectie" and isinstance(waarde, dict):
            gespeld[naam] = _selectievariant(rng, waarde)
        else:
            gespeld[naam] = waarde
    if tool == "query_data":
        # Leeg, afwezig en de default zijn dezelfde aanroep.
        if rng.random() < 0.3:
            gespeld.setdefault("max_rows", DUO_ROW_LIMIT)
        if "filters" not in gespeld and rng.random() < 0.3:
            gespeld["filters"] = rng.choice([None, {}])
        if rng.random() < 0.3:
            gespeld["columns"] = rng.choice([None, []])
    return _schud(rng, gespeld)

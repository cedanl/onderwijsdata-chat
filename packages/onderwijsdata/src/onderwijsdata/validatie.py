"""Details- en validatielaag boven properties/dimension/definitions/data.

Offline cataloguscheck eerst; live detailcheck (gecachet) alleen met ``live=True``.
Een titel die lijkt op een andere titel is nooit bewijs: ambiguïteit leidt tot een
verduidelijkingsvraag, ontbrekende kennis tot ``unknown`` en tijdelijke bronuitval
nooit tot "dataset bestaat niet". Een requirement die niet verwerkt kan worden
verdwijnt nooit stilzwijgend: die maakt de uitkomst ``unknown`` of ``unsupported``.
"""
import difflib

from . import contract
from .contract import SUPPORTED, UNSUPPORTED, UNKNOWN

# Periodetypes en hun CBS-formaatcode; prognosejaar heeft geen eigen code.
PERIODE_FORMAAT = {"jaar": "JJ", "schooljaar": "SJ", "kwartaal": "KW", "maand": "MM"}
GEO_NIVEAUS = ("landelijk", "corop", "provincie", "gemeente", "landsdeel")
# Regiocode-prefix per niveau (CBS-conventie); landelijk is exact NL01.
GEO_PREFIX = {"gemeente": "GM", "provincie": "PV", "corop": "CR", "landsdeel": "LD"}
LANDELIJK_CODE = "NL01"

# Toegestane requirementvelden; al het andere wordt gemeld, nooit genegeerd.
REQUIREMENT_VELDEN = ("sector", "geografie", "periode", "meetwaarden", "dimensies")
PERIODE_VELDEN = ("type", "jaar")
# Exacte titels waaraan een sectorcode in een uitsplitsende dimensie herkend wordt.
SECTOR_TITELS = {
    "mbo": ("middelbaar beroepsonderwijs", "mbo"),
    "hbo": ("hoger beroepsonderwijs", "hbo"),
    "wo": ("wetenschappelijk onderwijs", "wo"),
}


def _check(veld: str, status: str, reden: str | None = None, **extra) -> dict:
    return {"veld": veld, "status": status, "reden": reden, **extra}


def _suggesties(gezocht: str, opties: list[str], n: int = 3) -> list[str]:
    return difflib.get_close_matches(gezocht, opties, n=n, cutoff=0.5)


def _samenvatten(checks: list[dict]) -> str:
    statussen = {c["status"] for c in checks}
    if UNSUPPORTED in statussen:
        return UNSUPPORTED
    if UNKNOWN in statussen:
        return UNKNOWN
    return SUPPORTED


def _check_vorm(requirements) -> list[dict]:
    """Vorm en toegestane velden; een onverwerkte constraint mag niet succesvol verdwijnen."""
    if not isinstance(requirements, dict):
        return [_check("requirements", UNSUPPORTED, "requirements moet een dict zijn", fout="ongeldige_vorm")]
    checks = []
    for veld in requirements:
        if veld not in REQUIREMENT_VELDEN:
            checks.append(_check(veld, UNKNOWN, f"requirement {veld!r} wordt niet verwerkt",
                                 fout="onbekende_requirement", herstel=list(REQUIREMENT_VELDEN)))
    typen = {"sector": str, "geografie": str, "periode": dict, "meetwaarden": list, "dimensies": dict}
    for veld, typ in typen.items():
        if veld in requirements and not isinstance(requirements[veld], typ):
            checks.append(_check(veld, UNSUPPORTED, f"{veld} moet een {typ.__name__} zijn", fout="ongeldige_vorm"))
    return checks


def _live_waarden(rec: dict, dim: str) -> tuple[dict[str, str] | None, dict | None]:
    """(waarden, None) of (None, unknown-check) bij tijdelijke bronuitval."""
    from httpx import HTTPError
    try:
        return contract.dimensie_waarden(rec["dataset_id"], dim), None
    except HTTPError as e:
        return None, _check(dim, UNKNOWN, f"bron tijdelijk niet bereikbaar ({type(e).__name__})",
                            fout="bron_niet_bereikbaar", dimensie=dim)


def _sectordimensie(rec: dict) -> str | None:
    return next((d for d in rec["dimensies"] if "onderwijssoort" in d.lower()), None)


def _check_sector(rec: dict, sector: str, live: bool) -> dict:
    """Is de sector leverbaar, en (live) met welke geverifieerde code in welke dimensie?"""
    sector = sector.lower()
    if sector not in contract.SECTOREN:
        return _check("sector", UNSUPPORTED, f"{sector!r} valt buiten mbo/hbo/wo", fout="ongeldige_sector",
                      herstel=list(contract.SECTOREN))
    status = rec["scopeprofiel"][sector]
    if status == UNSUPPORTED:
        return _check("sector", UNSUPPORTED, f"tabel dekt {sector} niet ({rec['onderwijssectoren']})")
    if status == UNKNOWN:
        return _check("sector", UNKNOWN, "sectordeel niet aantoonbaar apart selecteerbaar (gemengde of brede tabel)")
    gedekt = [s for s in contract.SECTOREN if rec["scopeprofiel"][s] == SUPPORTED]
    if gedekt == [sector]:
        return _check("sector", SUPPORTED, sector=sector, filter_nodig=False)
    dim = _sectordimensie(rec)
    if dim is None:
        return _check("sector", UNKNOWN,
                      f"tabel dekt {'/'.join(gedekt)} samen; geen uitsplitsende dimensie bekend",
                      sector=sector, fout="sectorfilter_onbekend")
    if not live:
        return _check("sector", SUPPORTED, f"tabel dekt {'/'.join(gedekt)}; sectorcode in {dim} alleen live te bepalen",
                      sector=sector, dimensie=dim, filter_nodig=True, code=None)
    waarden, fout = _live_waarden(rec, dim)
    if fout:
        return {**fout, "veld": "sector"}
    titels = SECTOR_TITELS[sector]
    treffers = [k for k, t in waarden.items() if t.strip().lower() in titels]
    if len(treffers) != 1:
        return _check("sector", UNKNOWN, f"geen eenduidige {sector}-code in {dim}", sector=sector, dimensie=dim,
                      fout="sectorfilter_onbekend", opties=[f"{k} ({t})" for k, t in waarden.items()])
    return _check("sector", SUPPORTED, sector=sector, dimensie=dim, filter_nodig=True, code=treffers[0],
                  titel=waarden[treffers[0]])


def _regiodimensie(rec: dict) -> str | None:
    return next((d for d in rec["dimensies"] if "regio" in d.lower() or "gemeente" in d.lower()), None)


def _check_geografie(rec: dict, niveau: str) -> dict:
    geo = rec["geografie"]
    if geo["status"] == UNSUPPORTED:
        reden = geo.get("reden") or "tabel heeft geen regiodimensie"
        return _check("geografie", UNSUPPORTED, reden, fout="niet_ondersteund_niveau", herstel=geo["niveaus"])
    if geo["status"] == UNKNOWN:
        return _check("geografie", UNKNOWN, geo.get("reden"))
    if niveau not in geo["niveaus"]:
        return _check("geografie", UNSUPPORTED, f"niveau {niveau!r} niet beschikbaar", fout="niet_ondersteund_niveau",
                      herstel=geo["niveaus"])
    dim = _regiodimensie(rec) if geo.get("regionale_uitsplitsing") else None
    return _check("geografie", SUPPORTED, niveau=niveau, dimensie=dim)


def _check_periode(rec: dict, periode: dict, live: bool) -> dict:
    onbekend = [k for k in periode if k not in PERIODE_VELDEN]
    if onbekend:
        return _check("periode", UNKNOWN, f"periodeveld(en) {onbekend} worden niet verwerkt",
                      fout="onbekende_requirement", herstel=list(PERIODE_VELDEN))
    soort = periode.get("type")
    formaat = rec["perioden"]["formaat"]
    if soort not in PERIODE_FORMAAT:
        reden = ("prognosejaar heeft geen conversieregel naar de tabelperiode" if soort == "prognosejaar"
                 else f"onbekend periodetype {soort!r}")
        return _check("periode", UNSUPPORTED if soort == "prognosejaar" else UNKNOWN, reden, fout="periodetype")
    if not formaat:
        return _check("periode", UNKNOWN, "periodeformaat van de tabel onbekend")
    if PERIODE_FORMAAT[soort] not in formaat:
        return _check("periode", UNSUPPORTED,
                      f"{soort} ({PERIODE_FORMAAT[soort]}) is niet gelijk aan tabelperiode {formaat}; geen conversieregel",
                      fout="periodetype", herstel=formaat)
    if "jaar" not in periode:
        return _check("periode", SUPPORTED, type=soort)
    jaar = periode["jaar"]
    if not isinstance(jaar, int) or isinstance(jaar, bool):
        return _check("periode", UNSUPPORTED, "jaar moet een geheel getal zijn", fout="ongeldige_vorm")
    if soort not in ("jaar", "schooljaar"):
        return _check("periode", UNKNOWN, f"jaar zonder {soort}nummer is geen eenduidige periodecode",
                      fout="ontbrekende_selectie")
    code = f"{jaar}{PERIODE_FORMAAT[soort]}00"
    if not live:
        return _check("periode", UNKNOWN, f"periodecode {code} alleen live te verifiëren", type=soort, code=code)
    waarden, fout = _live_waarden(rec, "Perioden")
    if fout:
        return {**fout, "veld": "periode"}
    if code not in waarden:
        return _check("periode", UNSUPPORTED, f"periode {code} komt niet voor in deze tabel", fout="ongeldige_periode",
                      herstel=list(waarden)[-3:])
    return _check("periode", SUPPORTED, type=soort, dimensie="Perioden", code=code, titel=waarden[code])


def _check_meetwaarden(rec: dict, gevraagd: list[str]) -> list[dict]:
    per_key = {m["key"]: m for m in rec["meetwaarden"]}
    titels = {m["title"]: m["key"] for m in rec["meetwaarden"] if m["title"]}
    checks, eenheden = [], set()
    for mw in gevraagd:
        if mw in per_key:
            m = per_key[mw]
            eenheden.add(m["unit"])
            checks.append(_check("meetwaarde", SUPPORTED, key=mw, eenheid=m["unit"], titel=m["title"]))
        elif mw in titels:
            checks.append(_check("meetwaarde", UNSUPPORTED, "titel is geen sleutel; gebruik de officiële key",
                                 fout="titel_i_p_v_key", herstel=[titels[mw]]))
        else:
            checks.append(_check("meetwaarde", UNSUPPORTED, f"{mw!r} bestaat niet in deze tabel",
                                 fout="ongeldige_meetwaarde",
                                 herstel=_suggesties(mw, list(per_key) + list(titels))))
    if len(eenheden) > 1:
        checks.append(_check("meetwaarden_eenheid", UNKNOWN,
                             f"verschillende eenheden {sorted(eenheden)}: niet optellen of vergelijken zonder definitie",
                             fout="definitieverschil"))
    return checks


def _canonieke_dimensie(rec: dict, dim: str, live: bool) -> tuple[str | None, str | None, str]:
    """(titel, key, status) voor een dimensie opgegeven als officiële key óf titel.

    Eerst offline (titels + vastgelegde sleutels), daarna live via DataProperties.
    """
    sleutels = rec.get("dimensie_sleutels") or {}
    bekend = sleutels.get("sleutels") if sleutels.get("status") == SUPPORTED else None
    if dim in rec["dimensies"]:
        return dim, (bekend or {}).get(dim), SUPPORTED
    if bekend:
        for titel, key in bekend.items():
            if key == dim:
                return titel, key, SUPPORTED
    if live:
        from httpx import HTTPError
        try:
            key = contract.dimensie_sleutel(rec["dataset_id"], dim)
        except HTTPError:
            return None, None, UNKNOWN
        if key:
            titel = next((t for t, k in (bekend or {}).items() if k == key), None)
            return titel or dim, key, SUPPORTED
        return None, None, UNSUPPORTED
    # Offline zonder vastgelegde sleutels kan een onbekende naam nog een officiële key zijn.
    return None, None, UNSUPPORTED if bekend else UNKNOWN


def _check_dimensies(rec: dict, dims: dict[str, str], live: bool) -> list[dict]:
    checks = []
    for dim, code in dims.items():
        titel, sleutel, status = _canonieke_dimensie(rec, dim, live)
        if status != SUPPORTED:
            reden = (f"{dim!r} is geen dimensie van deze tabel" if status == UNSUPPORTED
                     else f"{dim!r} niet als titel bekend; officiële key alleen live te verifiëren")
            checks.append(_check("dimensie", status, reden,
                                 fout="ongeldige_dimensie" if status == UNSUPPORTED else "dimensie_onbevestigd",
                                 herstel=_suggesties(dim, rec["dimensies"])))
            continue
        if not live:
            checks.append(_check("dimensiecode", UNKNOWN, "codes alleen live te verifiëren", dimensie=titel,
                                 sleutel=sleutel))
            continue
        waarden, fout = _live_waarden(rec, sleutel or titel)
        if fout:
            checks.append({**fout, "veld": "dimensiecode", "dimensie": titel})
            continue
        if code in waarden:
            checks.append(_check("dimensiecode", SUPPORTED, dimensie=titel, sleutel=sleutel, code=code,
                                 titel=waarden[code]))
        else:
            checks.append(_check("dimensiecode", UNSUPPORTED, f"{code!r} is geen geldige code van {titel}",
                                 fout="ongeldige_code", dimensie=titel,
                                 herstel=[f"{k} ({t})" for k, t in waarden.items() if t in _suggesties(code, list(waarden.values()))][:3]))
    return checks


def _vereiste_code(c: dict) -> tuple[str, str, str] | None:
    """(dimensie, code, omschrijving) als deze check één concrete dimensiecode vastlegt."""
    if not (c.get("dimensie") and c.get("code")):
        return None
    if c["veld"] == "dimensiecode":
        return c["dimensie"], c["code"], f"{c['dimensie']}={c['code']!r}"
    if c["veld"] == "sector":
        return c["dimensie"], c["code"], f"sector {c['sector']} ({c['dimensie']}={c['code']})"
    if c["veld"] == "periode":
        return c["dimensie"], c["code"], f"periode {c['type']} ({c['dimensie']}={c['code']})"
    return None


def _check_samenhang(checks: list[dict]) -> list[dict]:
    """Constraints mogen elkaar niet tegenspreken (bv. sector hbo + WO-code, jaar 2023 + code
    2022SJ00, gemeente + provinciecode). Bij conflict wordt nooit stil één waarde gekozen."""
    per_dim: dict[str, dict[str, str]] = {}
    for c in checks:
        if v := _vereiste_code(c):
            per_dim.setdefault(v[0], {}).setdefault(v[1], v[2])
    codes = {dim: next(iter(vs)) for dim, vs in per_dim.items()}
    extra = []
    for dim, vs in per_dim.items():
        if len(vs) > 1:
            extra.append(_check("samenhang", UNSUPPORTED,
                                f"tegenstrijdige waarden voor {dim}: " + " vs ".join(vs.values()),
                                fout="tegenstrijdige_selectie", dimensie=dim, herstel=sorted(vs)))
    for c in checks:
        if c["veld"] == "geografie" and c["status"] == SUPPORTED and c.get("dimensie") in codes:
            gegeven = codes[c["dimensie"]]
            past = (gegeven == LANDELIJK_CODE if c["niveau"] == "landelijk"
                    else gegeven.startswith(GEO_PREFIX.get(c["niveau"], "\0")))
            if not past:
                extra.append(_check("samenhang", UNSUPPORTED,
                                    f"regiocode {gegeven!r} hoort niet bij niveau {c['niveau']!r}",
                                    fout="tegenstrijdige_selectie"))
    return extra


def validate_selection(dataset_id: str, requirements: dict, live: bool = False) -> dict:
    """Controleer of deze tabel de gevraagde selectie kan leveren.

    ``requirements`` (alle optioneel): ``sector`` ('mbo'|'hbo'|'wo'), ``geografie``
    (niveau), ``periode`` ({'type': 'jaar'|'schooljaar'|'kwartaal'|'maand'|'prognosejaar',
    'jaar': int}), ``meetwaarden`` (lijst keys), ``dimensies`` ({dimensie-key of -titel: code}).
    Andere velden worden niet genegeerd maar maken de uitkomst ``unknown``.

    Retourneert ``{"dataset_id", "status", "checks"}`` met status
    supported/unsupported/unknown. ``supported`` betekent: de tabel kan dit leveren;
    of een concrete query volledig is, bepaalt :func:`prepare_query`.
    Onbekende dataset-ID: ``DatasetNietGevonden``.
    """
    rec = contract.get_dataset(dataset_id)
    checks: list[dict] = _check_vorm(requirements)
    if any(c["status"] == UNSUPPORTED for c in checks):
        return {"dataset_id": rec["dataset_id"], "status": UNSUPPORTED, "checks": checks}
    if "sector" in requirements:
        checks.append(_check_sector(rec, requirements["sector"], live))
    if "geografie" in requirements:
        checks.append(_check_geografie(rec, requirements["geografie"]))
    if "periode" in requirements:
        checks.append(_check_periode(rec, requirements["periode"], live))
    if "meetwaarden" in requirements:
        checks.extend(_check_meetwaarden(rec, requirements["meetwaarden"]))
    if "dimensies" in requirements:
        checks.extend(_check_dimensies(rec, requirements["dimensies"], live))
    checks.extend(_check_samenhang(checks))
    if rec["archief"]["gearchiveerd"]:
        checks.append(_check("archief", SUPPORTED, "tabel is gearchiveerd; historische data", waarschuwing=True))
    return {"dataset_id": rec["dataset_id"], "status": _samenvatten(checks), "checks": checks}


def resolve_dimensiewaarde(dataset_id: str, dimensie: str, tekst: str) -> dict:
    """Koppel vrije tekst aan een geverifieerde dimensiecode (live, gecachet).

    Alleen exacte code- of titelmatch (hoofdletterongevoelig). Meerdere treffers
    of geen treffer leidt tot een verduidelijkingsvraag, nooit tot de eerste match.
    """
    from httpx import HTTPError
    try:
        waarden = contract.dimensie_waarden(dataset_id, dimensie)
    except HTTPError as e:
        return {"status": UNKNOWN, "fout": "bron_niet_bereikbaar", "reden": type(e).__name__}
    t = tekst.strip().lower()
    treffers = [(k, v) for k, v in waarden.items() if k.lower() == t or v.lower() == t]
    if len(treffers) == 1:
        return {"status": SUPPORTED, "code": treffers[0][0], "titel": treffers[0][1]}
    if treffers:
        return {"status": UNKNOWN, "fout": "ambigu", "opties": [{"code": k, "titel": v} for k, v in treffers]}
    opties = [{"code": k, "titel": v} for k, v in waarden.items() if v in _suggesties(tekst, list(waarden.values()))]
    return {"status": UNKNOWN, "fout": "geen_exacte_match", "opties": opties}


def _filters(rec: dict, checks: list[dict]) -> tuple[dict[str, str], list[dict]]:
    """Concrete filters per dimensie uit de checks, plus checks voor ontbrekende selecties."""
    filters: dict[str, str] = {}
    ontbrekend: list[dict] = []
    for c in checks:
        if c["veld"] == "dimensiecode":
            filters[c["dimensie"]] = c["code"]
    for c in checks:
        if c["veld"] == "sector" and c.get("filter_nodig"):
            filters.setdefault(c["dimensie"], c["code"])
        elif c["veld"] == "periode" and c.get("code"):
            filters.setdefault(c["dimensie"], c["code"])
        elif c["veld"] == "geografie" and c.get("dimensie"):
            if c["niveau"] == "landelijk":
                waarden, fout = _live_waarden(rec, c["dimensie"])
                if fout or LANDELIJK_CODE not in waarden:
                    ontbrekend.append({**fout, "veld": "geografie"} if fout else _check("geografie", UNKNOWN, f"{LANDELIJK_CODE} niet gevonden in "
                                                     f"{c['dimensie']}", fout="ontbrekende_selectie"))
                else:
                    filters.setdefault(c["dimensie"], LANDELIJK_CODE)
            elif c["dimensie"] not in filters:
                ontbrekend.append(_check("geografie", UNKNOWN,
                                         f"niveau {c['niveau']!r} vraagt een concrete regiocode in {c['dimensie']}",
                                         fout="ontbrekende_selectie", dimensie=c["dimensie"]))
    return filters, ontbrekend


def prepare_query(dataset_id: str, requirements: dict) -> dict:
    """Bouw ``$select``/``$filter`` alleen uit geverifieerde sleutels en codes (live).

    Iedere sector-, geografie- en periodevoorwaarde wordt een concreet filter; lukt
    dat niet, dan is de status ``unknown`` met de ontbrekende selectie in ``checks``.
    Retourneert ``{"status", "query", "checks"}``; ``query`` is ``None`` tenzij alles
    `supported` is. Een vrije NL-vraag wordt hier nooit automatisch een query.
    """
    result = validate_selection(dataset_id, requirements, live=True)
    result["query"] = None
    if result["status"] != SUPPORTED:
        return result
    rec = contract.get_dataset(dataset_id)
    filters, ontbrekend = _filters(rec, result["checks"])
    if ontbrekend:
        result["checks"].extend(ontbrekend)
        result["status"] = _samenvatten(result["checks"])
        return result
    query: dict[str, str] = {}
    keys = [c["key"] for c in result["checks"] if c["veld"] == "meetwaarde"]
    if keys:
        query["$select"] = ",".join(keys)
    sleutels = {c["dimensie"]: c.get("sleutel") for c in result["checks"] if c["veld"] == "dimensiecode"}
    vastgelegd = (rec.get("dimensie_sleutels") or {}).get("sleutels") or {}
    delen = []
    for dim, code in filters.items():
        sleutel = (sleutels.get(dim) or vastgelegd.get(dim)
                   or contract.dimensie_sleutel(rec["dataset_id"], dim) or dim)
        delen.append(f"trim({sleutel}) eq '{code}'")
    if delen:
        query["$filter"] = " and ".join(delen)
    result["query"] = query
    return result

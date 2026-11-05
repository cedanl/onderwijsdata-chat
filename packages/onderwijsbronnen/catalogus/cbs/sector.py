"""
Sectorclassificatie op productscope: uitsluitend mbo, hbo en wo.

Regelgebaseerd en met motivatie, zodat elke opname of uitsluiting te herleiden is.
`unknown` betekent: nog niet vast te stellen, dus eerst reviewen, niet toelaten.
"""
import re

IN_SCOPE = ("mbo", "hbo", "wo")

MBO, HBO, WO, GEMENGD, BUITEN, ONBEKEND = "mbo", "hbo", "wo", "gemengd", "buiten_scope", "onbekend"
# classificatie-waarden die als "in scope" tellen
TOEGELATEN = {MBO, HBO, WO, "ho", "gemengd_met_uitsplitsing"}

_PATRONEN = {
    "mbo": re.compile(r"\bmbo\b|middelbaar beroepsonderwijs|\bbol\b|\bbbl\b", re.I),
    "hbo": re.compile(r"\bhbo\b|hoger beroepsonderwijs", re.I),
    "wo": re.compile(r"\bwo\b|wetenschappelijk onderwijs|universitair", re.I),
    "ho": re.compile(r"\bho\b|hoger onderwijs", re.I),
    "po": re.compile(r"primair onderwijs|basisonderwijs|\bpo\b|speciaal onderwijs|\bso\b|\bsbo\b|basisschool", re.I),
    "vo": re.compile(r"voortgezet onderwijs|\bvo\b|vmbo|\bhavo\b|\bvwo\b|examen|voortgezet speciaal", re.I),
}
_ARBEIDSMARKT = re.compile(r"arbeidsmarkt|werkzame|werkloos|baan|beroepsbevolking|loon|inkomen|uwv", re.I)
# Dimensies die een sectoruitsplitsing mogelijk maken
_SECTOR_DIM = re.compile(r"onderwijssoort|sector|soort onderwijs|onderwijstype|schoolsoort|onderwijsvorm|niveau", re.I)


def _sectoren(tekst: str) -> set[str]:
    return {naam for naam, p in _PATRONEN.items() if p.search(tekst)}


def classificeer_sector(titel: str, thema: str = "", dimensies: list[str] | None = None) -> dict:
    """Classificeer een tabel; retourneert {classificatie, sectoren, motivatie, arbeidsmarkt_only}.

    classificatie: mbo | hbo | wo | ho | gemengd_met_uitsplitsing | gemengd_onscheidbaar
                   | buiten_scope | onbekend
    `ho` (hbo+wo) is alleen toelaatbaar voor aparte hbo/wo-cijfers als een
    sectordimensie bestaat; anders blijft de status `onbekend`.
    """
    dims = dimensies or []
    gevonden = _sectoren(titel) | _sectoren(thema)
    in_scope = gevonden & {"mbo", "hbo", "wo", "ho"}
    uit_scope = gevonden & {"po", "vo"}
    heeft_uitsplitsing = any(_SECTOR_DIM.search(d) for d in dims)
    arbeidsmarkt_only = not gevonden and bool(_ARBEIDSMARKT.search(titel + " " + thema))

    def res(klasse, motivatie, sectoren=None):
        return {"classificatie": klasse, "sectoren": sorted(sectoren if sectoren is not None else gevonden),
                "motivatie": motivatie, "arbeidsmarkt_only": arbeidsmarkt_only}

    if in_scope and uit_scope:
        if heeft_uitsplitsing:
            return res("gemengd_met_uitsplitsing",
                       f"mbo/hbo/wo naast {sorted(uit_scope)}; sectordimensie aanwezig, selectie nog te verifiëren")
        return res("gemengd_onscheidbaar", f"mbo/hbo/wo gemengd met {sorted(uit_scope)} zonder sectordimensie")
    if uit_scope:
        return res(BUITEN, f"alleen {sorted(uit_scope)}: buiten productscope")
    if in_scope == {"ho"} or in_scope == {"hbo", "wo"} or in_scope == {"hbo", "wo", "ho"}:
        if heeft_uitsplitsing:
            return res("ho", "ho/hbo+wo met sectordimensie: hbo en wo mogelijk apart selecteerbaar (te verifiëren)")
        return res(ONBEKEND, "ho-label bewijst geen aparte hbo/wo-cijfers; geen sectordimensie")
    if in_scope:
        klasse = next(iter(in_scope & {"mbo", "hbo", "wo"}), None)
        if len(in_scope) == 1 and klasse:
            return res(klasse, f"sector {klasse} in titel of thema")
        return res("gemengd_met_uitsplitsing" if heeft_uitsplitsing else GEMENGD,
                   f"meerdere in-scope sectoren {sorted(in_scope)}")
    if arbeidsmarkt_only:
        return res(BUITEN, "arbeidsmarkt-only zonder mbo/hbo/wo-sector: niet automatisch toevoegen", sectoren=[])
    return res(ONBEKEND, "geen sector in titel of thema; review nodig", sectoren=[])


def is_toegelaten(klasse: str) -> bool:
    return klasse in TOEGELATEN

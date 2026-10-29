"""Het recept per data-key van een gebruiker: hoe hij ontstond, zodat hij een herstart overleeft (#472).

Zodra een tool een key oplevert, onthoudt de sessie hier zijn recept, uit de aanroep die de
server zelf deed. Welk gesprek dat is weet de server dan nog niet: het gesprek-id kiest de
frontend. Bij het opslaan van het gesprek gaan de recepten van alle data waarop het rust
(de keys die de stappen meldden, met hun ouders) naar de database. Opzoeken gaat altijd per
gebruiker: nooit via het recept van een ander.
"""

from collections import OrderedDict

from persistence import db
from tools import herlaad, store
from tools.schemas import TOOL_RUN_ANALYSIS
from tools.snippet import Receptbron

# Wacht tot het gesprek is opgeslagen. Begrensd: een gesprek dat nooit wordt opgeslagen blijft niet hangen.
_MAX_WACHTEND = 2000
_wachtend: OrderedDict[tuple[str, str], dict] = OrderedDict()

# Welke keys een gebruiker in dit proces zelf live maakte (#762). Los van `_wachtend`: daar haalt het verwijderen van een
# ander gesprek met dezelfde key het recept weg, en de LRU verdringt het, terwijl de data nog die van zijn antwoord is.
# Alleen "verwijder al mijn gegevens" en een herstart legen dit. Begrensd door eerst keys te laten vallen die de store
# niet meer heeft: komen die terug, dan zijn ze opnieuw opgehaald en hoort de melding er wel.
_MAX_LIVE = 5000
_live: OrderedDict[tuple[str, str], None] = OrderedDict()


def van_session(session: dict) -> Receptbron:
    """De receptopzoeker voor de snippets van een sessie (#624): alleen de eigen gebruiker.

    Zelfde vorm als Receptbron uit tools.snippet: per key het recept waarmee hij ontstond,
    zodat een afgeleide snippet de stappen van zijn ouder kan herhalen. Een eigen berekening
    krijgt daarbij haar script mee uit het geheugen van deze sessie (data_provenance): het
    recept zelf bewaart geen script (#472), dus na een herstart blijft voor zo'n stap de kopie
    van de rijen over.
    """
    username = session.get("username")

    def van(key: str) -> dict | None:
        if not isinstance(username, str):
            return None
        return _met_script(voor(username, key), (session.get("data_provenance") or {}).get(key))

    return van


def _met_script(recept: dict | None, aanroep: object) -> dict | None:
    """Het recept van een eigen berekening met het script van de aanroep die haar maakte."""
    if recept is None or recept.get("stap") != herlaad.STAP_ANALYSE or "tool" in recept:
        return recept
    args = aanroep.get("arguments") if isinstance(aanroep, dict) and aanroep.get("name") == TOOL_RUN_ANALYSIS else None
    code = args.get("code") if isinstance(args, dict) else None
    if not isinstance(code, str):
        return recept
    return {**recept, "tool": TOOL_RUN_ANALYSIS, "args": {"code": code}}


def onthoud(username: str, key: str, recept: dict) -> None:
    """Leg het recept van `key` vast; de eerste maker is de echte, zoals bij de herkomst."""
    _wachtend.setdefault((username, key), recept)
    _wachtend.move_to_end((username, key))
    while len(_wachtend) > _MAX_WACHTEND:
        _wachtend.popitem(last=False)


def live(username: str | None, key: str) -> None:
    """`username` maakte `key` net zelf: zijn antwoord rust op de data zoals ze nu in de store staat (#472, #762)."""
    if not username:
        return
    herlaad.wis_markering(username, key)
    _live[username, key] = None
    _live.move_to_end((username, key))
    if len(_live) > _MAX_LIVE:
        for sleutel in [s for s in _live if store.meta(s[1]) is None]:
            del _live[sleutel]
    while len(_live) > _MAX_LIVE:
        _live.popitem(last=False)


def voor(username: str | None, key: str) -> dict | None:
    """Het recept van deze gebruiker voor `key`: nog in het geheugen, anders uit de database."""
    if not username:
        return None
    return _wachtend.get((username, key)) or db.recipe_for_key(username, key)


def bewaar(username: str, conv_id: str, messages: list) -> None:
    """Bewaar de recepten achter de data van een opgeslagen gesprek, ouders erbij."""
    recepten: dict[str, dict] = {}
    for key in _datakeys(messages):
        while isinstance(key, str) and key not in recepten and (recept := _wachtend.get((username, key))):
            recepten[key] = recept
            key = recept.get("afgeleid_van")
    db.save_recipes(username, conv_id, recepten)


def keys_van_gesprek(username: str, conv_id: object) -> list[str]:
    """De data-keys van een eigen, opgeslagen gesprek met een recept, ouders eerst.

    Een heropend gesprek kent zo zijn data weer; wat de store kwijt is, komt pas terug als een
    rapport erom vraagt (herstel_data_keys). Alleen de recepten van deze gebruiker.
    """
    if not isinstance(conv_id, str) or not conv_id:
        return []
    bewaard = db.recipes_for(username, conv_id)

    def diepte(key: str) -> int:
        stappen, ouder = 0, bewaard[key].get("afgeleid_van")
        while isinstance(ouder, str) and ouder in bewaard and stappen < len(bewaard):
            stappen, ouder = stappen + 1, bewaard[ouder].get("afgeleid_van")
        return stappen

    return sorted(bewaard, key=diepte)


def vergeet(username: str, keys) -> None:
    """Een verwijderd gesprek laat ook in het geheugen geen recept achter."""
    for key in keys:
        _wachtend.pop((username, key), None)


def vergeet_gebruiker(username: str) -> None:
    """Na "verwijder al mijn gegevens" (#646) geen recept van deze gebruiker meer, ook niet van een nooit opgeslagen
    gesprek: die staan niet in de database, dus `vergeet` met de keys daaruit mist ze."""
    for sleutel in [s for s in list(_wachtend) if s[0] == username]:
        _wachtend.pop(sleutel, None)
    for sleutel in [s for s in list(_live) if s[0] == username]:
        _live.pop(sleutel, None)
    herlaad.vergeet_gebruiker(username)


def terughalen(username: str | None, key: str) -> herlaad.Herlaadresultaat | None:
    """Zet `key` terug in de store als hij weg is; None als hij er is of geen recept heeft."""
    if store.get(key) is not None:
        markeer_na_herstart(username, key)
        return None
    if (recept := voor(username, key)) is None:
        return None
    return herlaad.herlaad(key, recept, lambda ouder: voor(username, ouder), username)


def markeer_na_herstart(username: str | None, key: str) -> None:
    """Markeer `key` voor deze gebruiker als herladen als hij hem vóór de laatste herstart maakte.

    Dan heeft hij er een recept van in de database, maar maakte hij de key in dit proces niet zelf live (#762). Wat de
    store nu onder die key heeft, haalde dit proces op: een recept, of de live vraag van een ander. Het eerdere
    antwoord van deze gebruiker rust niet op die data. Een ander merkt hier niets van (#788).
    """
    if not username or store.meta(key) is None or (username, key) in _live or herlaad.herladen_op(username, key):
        return
    if db.recipe_for_key(username, key) is not None:
        herlaad.markeer(username, key)


def wis() -> None:
    _wachtend.clear()
    _live.clear()
    herlaad.wis()


def _datakeys(messages: list) -> list[str]:
    """De data achter de stappen van een gesprek: de tabellen onder een antwoord (tools[].exportKey, #269) en
    de key die elke stap meldde (tools[].dataKey, #551), elk één keer, in volgorde.

    Alleen op exportKey kende een gesprek met een lader en een KPI, zonder selectie in de store, bij
    heropenen geen data meer: dan vroeg de app om eerst een nieuwe vraag te stellen."""
    keys = [
        tool[veld]
        for m in messages or []
        if isinstance(m, dict) and isinstance(m.get("tools"), list)
        for tool in m["tools"]
        if isinstance(tool, dict)
        for veld in ("exportKey", "dataKey")
        if isinstance(tool.get(veld), str)
    ]
    return list(dict.fromkeys(keys))

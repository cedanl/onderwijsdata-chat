"""Het gebruikersprofiel uit de websocket-actie `settings`, begrensd tot vaste waarden (#1020).

Het profiel is invoer van de client en gaat de systeemprompt in. Vrije tekst daarin is voor de getalcontrole
een "hard" getal dat de gebruiker niet zelf noemde, en een instructie aan het model. Daarom laat dit profiel
alleen bekende waarden door: een functie uit de vaste lijst, een sector van de app en een instelling uit het
register (als de canonieke registernaam). De rest valt stil weg; `model` gaat ongewijzigd door, want `_model`
in `routes/chat.py` begrenst dat al (#755). Ook een sleutel `geavanceerd` valt weg: die instelling komt alleen uit de
database (core/geavanceerd.py, #1269), nooit uit wat de client meestuurt.
"""

from data.instellingen import instellingsprofiel

# Gelijk aan FUNCTIES in frontend/src/functies.js (tests/test_profiel_begrensd.py houdt ze gelijk).
FUNCTIES = ("Bestuurder", "Directeur", "Beleidsmedewerker", "IR-specialist", "Onderzoeker", "Docent", "Anders")
DOMEINEN = ("mbo", "hbo", "wo")
# Een registernaam is veel korter; een langere opgave gaat niet eens het register in.
MAX_INSTELLING_CHARS = 200

_FUNCTIE_OP_KLEINE_LETTERS = {functie.lower(): functie for functie in FUNCTIES}


def _tekst(waarde: object) -> str:
    """De opgave zonder witruimte eromheen; alles wat geen tekst is telt als leeg."""
    return waarde.strip() if isinstance(waarde, str) else ""


def _functie(waarde: object) -> str | None:
    return _FUNCTIE_OP_KLEINE_LETTERS.get(_tekst(waarde).lower())


def _domein(waarde: object) -> str | None:
    domein = _tekst(waarde).lower()
    return domein if domein in DOMEINEN else None


def _instelling(waarde: object) -> str | None:
    """De registernaam bij een naam, alias of instellingscode; None als onbekend, te lang of zonder register."""
    opgave = _tekst(waarde)
    if not opgave or len(opgave) > MAX_INSTELLING_CHARS:
        return None
    profiel = instellingsprofiel(opgave)
    return profiel["naam"] if profiel else None


def normaliseer_profiel(settings: object) -> dict:
    """Alleen `model`, `functie`, `domein` en `instelling`, elk alleen als het geldig is; idempotent.

    `rol` is de oude naam van `functie` en geldt als terugval; hij wordt onder `functie` bewaard.
    """
    if not isinstance(settings, dict):
        return {}
    profiel: dict = {}
    if "model" in settings:
        profiel["model"] = settings["model"]
    waarden = {
        "functie": _functie(settings.get("functie")) or _functie(settings.get("rol")),
        "domein": _domein(settings.get("domein")),
        "instelling": _instelling(settings.get("instelling")),
    }
    profiel.update({sleutel: waarde for sleutel, waarde in waarden.items() if waarde})
    return profiel

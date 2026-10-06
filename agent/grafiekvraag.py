"""Een grafiekvraag met data levert een grafiek, of zegt waarom niet (#221).

Of er een grafiek komt, lag bij het model. Live gaf "maak een staafgrafiek" python-code
als tekst (`fig = px.bar(...)`), schreef gpt-oss "Staafgrafiek …" als placeholder zonder
grafiek, en werd een gevraagde lijngrafiek een staafgrafiek. Hier leest code de vraag:
vraagt die om een grafiek (en welk type), dan toetst de controle het antwoord daaraan.

Zonder grafiekverzoek zegt deze controle niets: geen vraag, geen grafiek (#85, #105).
"""

import re

from .probleem import Probleem
from .selectie import data_keys

# Per type de woorden waarmee een gebruiker het vraagt; "auto" is een grafiek zonder type.
_TYPEN: dict[str, str] = {
    "bar": r"staaf(?:grafiek|diagram)\w*|staafjes|kolomgrafiek\w*|bar ?charts?",
    "line": r"lijn(?:grafiek|diagram)\w*|line ?charts?",
    "pie": r"(?:taart|cirkel)(?:grafiek|diagram)\w*|pie ?charts?",
    "scatter": r"spreidingsdiagram\w*|puntenwolk\w*|scatter ?plots?",
    "histogram": r"histogram\w*",
    "auto": r"grafiek\w*|diagram\w*|charts?|plot|visualis\w+|grafisch\w*",
}
_PATRONEN = {t: re.compile(rf"\b(?:{p})\b", re.IGNORECASE) for t, p in _TYPEN.items()}
_ELK_TYPE = re.compile("|".join(f"(?:{p.pattern})" for p in _PATRONEN.values()), re.IGNORECASE)
# "zonder grafiek", "geen grafiek nodig": wie dat vraagt, vraagt er geen.
_ZONDER = re.compile(rf"\b(?:zonder|geen)\s+(?:\w+\s+)?(?:{_ELK_TYPE.pattern})", re.IGNORECASE)
# "wat betekent de grafiek?" gaat over een grafiek die er al is; alleen een verzoek telt.
_VERZOEK = re.compile(
    r"\b(?:maak|maken|toon|tonen|teken|tekenen|laat|geef|plot|visualiseer|visualiseren|zet|weergeven)\b"
    r"|\b(?:in|als)\s+(?:een\s+)?\w*(?:grafiek|diagram|chart)",
    re.IGNORECASE,
)
_BEPAALD = re.compile(r"\b(?:de|deze|die|dat|het|vorige|bovenstaande|getoonde)\s+$", re.IGNORECASE)

# Wat create_plot teruggeeft als de grafiek er is; zie tools/plot.py (_CHART_TYPE_LABELS).
_GEMAAKT = re.compile(r"^(Staafgrafiek|Lijngrafiek|Spreidingsdiagram|Taartdiagram|Histogram|Grafiek) '.*' aangemaakt")
_TYPE_VAN_LABEL = {
    "Staafgrafiek": "bar",
    "Lijngrafiek": "line",
    "Spreidingsdiagram": "scatter",
    "Taartdiagram": "pie",
    "Histogram": "histogram",
}
_NAAM = {
    "bar": "staafgrafiek",
    "line": "lijngrafiek",
    "pie": "taartdiagram",
    "scatter": "spreidingsdiagram",
    "histogram": "histogram",
}

# Grafiekcode als tekst is nooit de grafiek die gevraagd is.
_CODE = re.compile(r"\bfig\.show\(|\bpx\.\w+\(|\bplt\.\w+\(|\bgo\.Figure\(|\bimport (?:plotly|matplotlib)\b")
_ZIN = re.compile(r"[^.!?\n]+")
_ONTKENNING = re.compile(r"\b(?:geen|niet)\b", re.IGNORECASE)


def gevraagde_typen(vraag: str) -> set[str]:
    """De grafiektypen die de vraag noemt; {"auto"} voor een grafiek zonder type, leeg zonder grafiekverzoek."""
    if _ZONDER.search(vraag) or not _VERZOEK.search(vraag):
        return set()
    typen = {t for t, p in _PATRONEN.items() if t != "auto" and _nieuw(p, vraag)}
    if typen:
        return typen
    return {"auto"} if _nieuw(_PATRONEN["auto"], vraag) else set()


def _nieuw(patroon: re.Pattern, vraag: str) -> bool:
    """Noemt de vraag een grafiek die er nog niet is? "de grafiek" wijst naar een bestaande."""
    return any(not _BEPAALD.search(vraag[: m.start()]) for m in patroon.finditer(vraag))


def _gemaakte_typen(tool_results: list[str]) -> list[str]:
    return [_TYPE_VAN_LABEL.get(m.group(1), "auto") for r in tool_results if (m := _GEMAAKT.match(r.strip()))]


def _legt_uit(tekst: str) -> bool:
    """Een zin die zegt dat er geen grafiek is (of kan), met een reden die het model erbij schrijft."""
    return any(_ELK_TYPE.search(z) and _ONTKENNING.search(z) for z in _ZIN.findall(tekst))


def ontbrekende_grafiek(
    vraag: str, tekst: str, tool_results: list[str], eerdere_keys: list[str] | tuple = ()
) -> list[Probleem]:
    """Problemen als de vraag om een grafiek vraagt en het antwoord die niet levert."""
    typen = gevraagde_typen(vraag)
    if not typen:
        return []
    problemen: list[Probleem] = []
    if _CODE.search(tekst):
        problemen.append(
            Probleem(
                "Het antwoord geeft grafiekcode als tekst in plaats van een grafiek.",
                "Maak de grafiek met create_plot op de data_key van de opgehaalde data, of zeg waarom dat niet "
                "kan. Geen code in het antwoord.",
            )
        )
    gemaakt = _gemaakte_typen(tool_results)
    if not gemaakt:
        if (data_keys(tool_results) or eerdere_keys) and not _legt_uit(tekst):
            soort = _NAAM.get(next(iter(typen)), "grafiek") if len(typen) == 1 else "grafiek"
            problemen.append(
                Probleem(
                    f"De vraag vraagt om een {soort}, maar het antwoord heeft er geen.",
                    "Roep create_plot aan met de data_key van de opgehaalde data"
                    + (f" en chart_type '{next(iter(typen))}'" if soort != "grafiek" else "")
                    + ", of zeg in het antwoord waarom er geen grafiek kan komen.",
                )
            )
        return problemen
    gevraagd = typen - {"auto"}
    if len(gevraagd) == 1 and not gevraagd & set(gemaakt):
        (type_,) = gevraagd
        problemen.append(
            Probleem(
                f"De vraag vraagt om een {_NAAM[type_]}, maar de grafiek is een ander type.",
                f"Maak de grafiek opnieuw met create_plot en chart_type '{type_}'.",
            )
        )
    return problemen

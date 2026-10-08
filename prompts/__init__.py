from pathlib import Path

from core.config import SEARCH_CATALOG_LIMIT
from data.instellingen import instellingsprofiel

_PROMPT_DIR = Path(__file__).parent
_GEEN_VOORKEUR = "Geen voorkeur"

# Limieten komen uit de code, zodat prompt en afdwinging niet uit elkaar lopen (#52).
SYSTEM_PROMPT = (_PROMPT_DIR / "system.md").read_text().replace("{ZOEKLIMIET}", str(SEARCH_CATALOG_LIMIT))


def _instellingsgegevens(instelling: str) -> str | None:
    """Sector en regio van de profielinstelling uit de code, zodat het model geen provincie kiest (#448)."""
    profiel = instellingsprofiel(instelling)
    if profiel is None:
        return None
    delen = [f"sector **{profiel['sector']}**", f"instellingscode {profiel['instellingscode']}"]
    regio = [f"{niveau} **{profiel[niveau]}**" for niveau in ("provincie", "arbeidsmarktregio") if profiel[niveau]]
    regel = "- Instellingsgegevens (DUO-instellingsadres): " + ", ".join(delen + regio) + "."
    if regio:
        regel += (
            " Bij 'mijn regio': gebruik deze provincie of arbeidsmarktregio, wat de bron kent, en noem dat niveau"
            " in je antwoord."
        )
    if profiel["sector"] in ("hbo", "wo"):
        regel += (
            " In DUO-hbo/wo zijn `PROVINCIENAAM`/`GEMEENTENAAM` de vestiging van de instelling, niet de woonplaats"
            " van de student."
        )
    return regel


def build_persona_block(settings: dict) -> str:
    lines = []
    rol = settings.get("functie") or settings.get("rol", _GEEN_VOORKEUR)
    if rol and rol != _GEEN_VOORKEUR:
        lines.append(f"- Gebruikersrol: **{rol}** — stem taalgebruik en diepte van uitleg hierop af.")
    domein = settings.get("domein", _GEEN_VOORKEUR)
    if domein and domein != _GEEN_VOORKEUR:
        lines.append(
            f"- Domein: **{domein}** — prioriteer datasets en voorbeelden uit dit domein. Sla de scope-vraag naar onderwijsniveau over als {domein} dit al bepaalt."
        )
    instelling = (settings.get("instelling") or "").strip()
    if instelling:
        lines.append(
            f"- Instelling: **{instelling}** — dit is de instelling van de gebruiker. Gebruik deze naam bij vragen over 'mijn instelling' en sla de scope-vraag naar instellingsnaam over."
        )
        if gegevens := _instellingsgegevens(instelling):
            lines.append(gegevens)
    context = (settings.get("context") or "").strip()
    if context:
        lines.append(f"- Aanvullende context: {context}")
    if not lines:
        return ""
    return "\n\n## Gebruikersprofiel\n" + "\n".join(lines)

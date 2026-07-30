from pathlib import Path

_PROMPT_DIR = Path(__file__).parent
_GEEN_VOORKEUR = "Geen voorkeur"

SYSTEM_PROMPT = (_PROMPT_DIR / "system.md").read_text()


def build_persona_block(settings: dict) -> str:
    lines = []
    rol = settings.get("functie") or settings.get("rol", _GEEN_VOORKEUR)
    if rol and rol != _GEEN_VOORKEUR:
        lines.append(f"- Gebruikersrol: **{rol}** — stem taalgebruik en diepte van uitleg hierop af.")
    domein = settings.get("domein", _GEEN_VOORKEUR)
    if domein and domein != _GEEN_VOORKEUR:
        lines.append(f"- Domein: **{domein}** — prioriteer datasets en voorbeelden uit dit domein. Sla de scope-vraag naar onderwijsniveau over als {domein} dit al bepaalt.")
    instelling = (settings.get("instelling") or "").strip()
    if instelling:
        lines.append(f"- Instelling: **{instelling}** — dit is de instelling van de gebruiker. Gebruik deze naam bij vragen over 'mijn instelling' en sla de scope-vraag naar instellingsnaam over.")
    context = (settings.get("context") or "").strip()
    if context:
        lines.append(f"- Aanvullende context: {context}")
    if not lines:
        return ""
    return "\n\n## Gebruikersprofiel\n" + "\n".join(lines)

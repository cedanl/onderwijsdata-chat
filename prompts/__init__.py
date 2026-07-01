from pathlib import Path

_PROMPT_DIR = Path(__file__).parent

SYSTEM_PROMPT = (_PROMPT_DIR / "system.md").read_text()


def build_persona_block(settings: dict) -> str:
    lines = []
    rol = settings.get("rol", "Geen voorkeur")
    if rol and rol != "Geen voorkeur":
        lines.append(f"- Gebruikersrol: **{rol}** — stem taalgebruik en diepte van uitleg hierop af.")
    domein = settings.get("domein", "Geen voorkeur")
    if domein and domein != "Geen voorkeur":
        lines.append(f"- Domein: **{domein}** — prioriteer datasets en voorbeelden uit dit domein.")
    context = (settings.get("context") or "").strip()
    if context:
        lines.append(f"- Instelling / Regio: {context}")
    if not lines:
        return ""
    return "\n\n## Gebruikersprofiel\n" + "\n".join(lines)

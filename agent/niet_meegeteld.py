"""De regel "Niet meegeteld:" bovenaan een antwoord, uit code (#743).

Op "Wat is de instroom van de HvA?" telde het antwoord de eerstejaars in het hoger onderwijs (DUO p02ho1ejrs), en
pas na doorvragen bleek dat de masters ontbraken. Dat stond wel in de teldefinitie onder het antwoord, maar midden in
een lange DUO-alinea. Hier staat per telling in één regel wat er níét in zit, direct onder het Uitgangspunt (#620).
Alleen wat de teldefinitie van DUO zelf uitsluit; test_niet_meegeteld leest dat na in de catalogus.
"""

from tools import store
from tools.catalog import bron_naam

from .selectie import data_keys

KOP = "**Niet meegeteld:**"

NIET_MEEGETELD: dict[str, str] = {
    "p01hoinges": "een tweede inschrijving van dezelfde student (alleen de hoofdinschrijving telt), en opleidingen aan "
    "aangewezen instellingen",
    "p02ho1ejrs": "wie eerder in het hoger onderwijs stond ingeschreven, dus ook wie na een Nederlandse bachelor "
    "aan een master begint; hbo-masters; opleidingen aan aangewezen instellingen",
    "p04hogdipl": "propedeuse-, postinitiële en uitwisselingsdiploma's",
}


def regel(tool_results: list[str]) -> str | None:
    """De regel voor de DUO-tellingen van deze beurt die iets uitsluiten; None als er geen is."""
    datasets: list[str] = []
    for key in data_keys(tool_results):
        known = store.meta(key)
        if (
            known is not None
            and known.bron == "duo"
            and known.dataset in NIET_MEEGETELD
            and known.dataset not in datasets
        ):
            datasets.append(known.dataset)
    if not datasets:
        return None
    if len(datasets) == 1:
        return f"{KOP} {NIET_MEEGETELD[datasets[0]]}."
    return f"{KOP} " + "; ".join(f"{bron_naam(d)}: {NIET_MEEGETELD[d]}" for d in datasets) + "."


def met_niet_meegeteld(tekst: str, tool_results: list[str]) -> str:
    """Het antwoord met de regel ervoor, als de telling iets uitsluit."""
    gevonden = regel(tool_results) if tekst.strip() else None
    return f"{gevonden}\n\n{tekst}" if gevonden else tekst

"""De bestandskeuze per instelling en jaar (#1238) in gewone pandas, los van tools/duo_bestandskeuze.py.

Voor tests die een getal van het dashboard of de chat narekenen uit de DUO-fixtures: per sector (hbo, wo), instelling
en jaar de rijen van het bestand met de minste -1 in de telkolom, dan het hoogste totaal zonder -1, dan het eerste
bestand van de groep. De groepen staan hier als indexen in de gepinde catalogus, in groepsvolgorde.
"""

import pandas as pd

GROEPEN = {
    "p01hoinges": ((2, 0, 3), (4, 1, 5)),
    "p02ho1ejrs": ((3, 0, 2), (4, 1, 5)),
    "p03hoinschr": ((2, 0, 3), (4, 1, 5)),
    "p04hogdipl": ((3, 0, 2), (4, 1, 5)),
}
KOLOMMEN = {
    "p01hoinges": ("STUDIEJAAR", "AANTAL_INGESCHREVENEN"),
    "p02ho1ejrs": ("STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"),
    "p03hoinschr": ("STUDIEJAAR", "AANTAL_INSCHRIJVINGEN"),
    "p04hogdipl": ("DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN"),
}
_CODE = "INSTELLINGSCODE_ACTUEEL"


def gekozen(dataset_id: str) -> pd.DataFrame:
    """De ruwe rijen (met -1) van de gekozen bestanden van hbo en wo samen, zoals `duo.load` ze geeft."""
    return pd.concat([df for _, df in _per_bestand(dataset_id)], ignore_index=True)


def gebruikt(dataset_id: str) -> list[int]:
    """De bestanden die minstens één instelling en jaar leveren: eerst hbo, dan wo, elk in groepsvolgorde."""
    return [index for index, df in _per_bestand(dataset_id) if not df.empty]


def _per_bestand(dataset_id: str) -> list[tuple[int, pd.DataFrame]]:
    from onderwijsbronnen import duo

    jaar, waarde = KOLOMMEN[dataset_id]
    delen = []
    for groep in GROEPEN[dataset_id]:
        bestanden = {index: duo.load(dataset_id, index) for index in groep}
        tellingen = []
        for positie, (index, df) in enumerate(bestanden.items()):
            onderdrukt = df[waarde] == -1
            telling = df[[_CODE, jaar]].assign(onderdrukt=onderdrukt.astype(int), totaal=df[waarde].mask(onderdrukt))
            telling = telling.groupby([_CODE, jaar])[["onderdrukt", "totaal"]].sum().reset_index()
            tellingen.append(telling.assign(positie=positie, index=index))
        keuze = pd.concat(tellingen).sort_values(["onderdrukt", "totaal", "positie"], ascending=[True, False, True])
        keuze = keuze.drop_duplicates([_CODE, jaar])
        for index, df in bestanden.items():
            delen.append((index, df.merge(keuze.loc[keuze["index"] == index, [_CODE, jaar]])))
    return delen


def geslacht(dataset_id: str = "p01hoinges") -> pd.DataFrame:
    """De twee geslacht-bestanden (hbo 0, wo 1): alleen die hebben GESLACHT."""
    from onderwijsbronnen import duo

    return pd.concat([duo.load(dataset_id, 0), duo.load(dataset_id, 1)], ignore_index=True)

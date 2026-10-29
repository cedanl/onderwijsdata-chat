"""Geslacht per opleiding uit DUO, alleen waar het exact af te leiden is (#742).

DUO publiceert de ho-tellingen (p01, p02, p03) in losse bestanden per uitsplitsing. Het geslachtsbestand telt per
instelling, vestigingsgemeente, onderdeel, subonderdeel en type ho; het niveaubestand telt in diezelfde cellen per
opleiding, zonder geslacht. Dezelfde vraag ("de man-vrouwverhouding bij Luchtvaart van Inholland") kreeg zo de ene
keer een verdeling en de andere keer "niet beschikbaar": of het model de twee bestanden koppelde, besliste het per
run.

De koppeling is exact als de opleiding in een jaar de enige is in haar cel van het geslachtsbestand, er in die cel
niets onderdrukt is (-1), en de totalen van beide bestanden gelijk zijn. Dan is de verdeling van de cel die van de
opleiding. Anders geeft de code per jaar de reden en geen getal: geen schatting uit een cel met andere opleidingen,
en geen onderdrukte cel die uit een verschil terug te rekenen is.
"""

import difflib
from dataclasses import dataclass

import pandas as pd

GESLACHT = "GESLACHT"
CODE = "OPLEIDINGSCODE_ACTUEEL"
NAAM = "OPLEIDINGSNAAM_ACTUEEL"
AANDEEL = "AANDEEL_PROCENT"
# Zoveel andere opleidingen noemt een reden, zoveel namen een fout over een onbekende opleiding.
_MAX_NAMEN = 3
_MAX_VOORSTELLEN = 8


@dataclass(frozen=True)
class Opleiding:
    code: str
    naam: str


@dataclass(frozen=True)
class Verdeling:
    """De verdeling naar geslacht in de jaren waarin die exact is, en per ander jaar de reden."""

    rijen: pd.DataFrame
    niet_af_te_leiden: dict[int, str]


def _tekst(waarde) -> str:
    if pd.isna(waarde):
        return ""
    if isinstance(waarde, float) and waarde.is_integer():
        return str(int(waarde))
    return str(waarde).strip()


def _cellen(df: pd.DataFrame, sleutel: list[str]) -> pd.DataFrame:
    """De celkolommen als tekst, zodat een lege SUBONDERDEEL en 34278 tegenover 34278.0 gewoon gelijk zijn."""
    return df.assign(**{k: df[k].map(_tekst) for k in sleutel})


def kies_opleiding(niveau: pd.DataFrame, gevraagd: str) -> Opleiding | str:
    """De opleiding in de rijen van één instelling, op CROHO-code of naam; de fout als tekst. Geen gok.

    Een naam telt als hij gelijk is (hoofdletters niet), anders als deel van een naam ("Luchtvaart"). Meer dan één
    opleiding is een keuze voor het model, met de codes erbij.
    """
    tekst = " ".join(str(gevraagd or "").split())
    if not tekst:
        return "Geef de opleiding: haar naam of CROHO-code."
    opleidingen = (
        niveau.assign(**{CODE: niveau[CODE].map(_tekst)})
        .sort_values("STUDIEJAAR")
        .drop_duplicates(CODE, keep="last")[[CODE, NAAM]]
    )
    namen = opleidingen[NAAM].astype(str).str.lower()
    if tekst.isdigit():
        gevonden = opleidingen[opleidingen[CODE] == tekst]
    elif (namen == tekst.lower()).any():
        gevonden = opleidingen[namen == tekst.lower()]
    else:
        gevonden = opleidingen[namen.str.contains(tekst.lower(), regex=False)]
    if len(gevonden) == 1:
        return Opleiding(gevonden[CODE].iloc[0], str(gevonden[NAAM].iloc[0]))
    if len(gevonden) > 1:
        keuzes = "; ".join(f"{naam} ({code})" for code, naam in gevonden.itertuples(index=False))
        return f"Meer opleidingen passen bij {tekst!r}: {keuzes}. Geef de CROHO-code van de bedoelde."
    voorstellen = difflib.get_close_matches(
        tekst, opleidingen[NAAM].astype(str).tolist(), n=_MAX_VOORSTELLEN, cutoff=0.4
    )
    hint = f" Bedoel je een van deze: {'; '.join(voorstellen)}?" if voorstellen else ""
    return f"Geen opleiding {tekst!r} bij deze instelling in het bestand.{hint}"


def _reden(eigen: pd.DataFrame, in_cellen: pd.DataFrame, geslacht: pd.DataFrame, sleutel, waarde, opl) -> str | None:
    """Waarom de verdeling in dit jaar niet exact is; None als ze dat wel is."""
    andere = in_cellen[in_cellen[CODE] != opl.code]
    if not andere.empty:
        namen = sorted(set(andere[NAAM].astype(str)))
        meer = f" en {len(namen) - _MAX_NAMEN} andere" if len(namen) > _MAX_NAMEN else ""
        return (
            "het geslachtsbestand telt de opleiding samen met andere opleidingen in dezelfde vestiging en hetzelfde "
            f"onderdeel ({', '.join(namen[:_MAX_NAMEN])}{meer})"
        )
    if eigen[waarde].isna().any() or geslacht[waarde].isna().any():
        return "DUO onderdrukte kleine aantallen (-1) in deze cel"
    per_cel_opl = eigen.groupby(sleutel)[waarde].sum()
    per_cel_geslacht = geslacht.groupby(sleutel)[waarde].sum().reindex(per_cel_opl.index)
    if per_cel_geslacht.isna().any():
        return "het geslachtsbestand heeft geen rij voor de vestiging en het onderdeel van de opleiding"
    if (per_cel_opl.to_numpy(float) != per_cel_geslacht.to_numpy(float)).any():
        return (
            f"de totalen verschillen: {int(per_cel_opl.sum())} in het opleidingsbestand, "
            f"{int(per_cel_geslacht.sum())} in het geslachtsbestand"
        )
    return None


def verdeling(
    niveau: pd.DataFrame,
    geslacht: pd.DataFrame,
    opl: Opleiding,
    waarde: str,
    periodekolom: str = "STUDIEJAAR",
    instellingskolom: str = "INSTELLINGSCODE_ACTUEEL",
    jaren: tuple[int, ...] = (),
) -> Verdeling:
    """Per jaar de verdeling van `opl` naar geslacht als die exact is, anders de reden.

    `niveau` en `geslacht` zijn de rijen van één instelling, met -1 al gemaskeerd (NaN). De cel is wat beide
    bestanden delen behalve de telling: instelling, gemeente, onderdeel, subonderdeel, type ho en het jaar.
    """
    sleutel = [k for k in geslacht.columns if k in niveau.columns and k != waarde]
    niveau = _cellen(niveau.assign(**{CODE: niveau[CODE].map(_tekst)}), sleutel)
    geslacht = _cellen(geslacht, sleutel)
    eigen_alle = niveau[niveau[CODE] == opl.code]
    beschikbaar = sorted({int(j) for j in niveau[periodekolom]})
    rijen, niet = [], {}
    for jaar in jaren or tuple(beschikbaar):
        if jaar not in beschikbaar:
            niet[jaar] = "het bestand heeft dit studiejaar niet"
            continue
        eigen = eigen_alle[eigen_alle[periodekolom] == str(jaar)]
        if eigen.empty:
            niet[jaar] = "de opleiding staat dit jaar niet in het bestand"
            continue
        cellen = eigen[sleutel].drop_duplicates()
        in_cellen = niveau.merge(cellen, on=sleutel)
        van_geslacht = geslacht.merge(cellen, on=sleutel)
        if reden := _reden(eigen, in_cellen, van_geslacht, sleutel, waarde, opl):
            niet[jaar] = reden
            continue
        per = van_geslacht.groupby(GESLACHT, sort=True)[waarde].sum()
        totaal = per.sum()
        for geslachtswaarde, aantal in per.items():
            rijen.append(
                {
                    periodekolom: jaar,
                    instellingskolom: eigen[instellingskolom].iloc[0],
                    CODE: opl.code,
                    NAAM: opl.naam,
                    GESLACHT: geslachtswaarde,
                    waarde: int(aantal),
                    AANDEEL: round(100 * float(aantal) / float(totaal), 1) if totaal else None,
                }
            )
    kolommen = [periodekolom, instellingskolom, CODE, NAAM, GESLACHT, waarde, AANDEEL]
    return Verdeling(pd.DataFrame(rijen, columns=kolommen), niet)

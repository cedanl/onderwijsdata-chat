"""Accreditatiedata per ho-opleiding, uit DUO's Overzicht Erkenningen ho (#726, stap A).

DUO publiceert dagelijks per instelling en opleiding (CROHO) de erkenning, met de datums die de NVAO of de minister
over de accreditatie vastlegt (toelichting v1.8, CC-BY). Een oordeel van de NVAO (voldoende, goed, excellent), de
besluittekst of het rapport staat er niet in: dat publiceert alleen de NVAO, en die bron zit (nog) niet in de app.

Welke datum wat betekent, staat hier in code; het model formuleert alleen. Twee valkuilen uit het onderzoek van
30-10: de inleverdatum is de uiterste indiening van het visitatierapport voor de volgende beoordeling, geen einddatum
van de accreditatie; de vervaldatum hoort alleen bij de termijn van een nieuwe opleiding.

Het bestand komt via get_duo_data, zoals elke DUO-dataset: scopegrens, store, peilmoment en bronregel lopen mee.
Per instelling en opleiding kan het meer rijen hebben (per vestiging en vorm); de accreditatiedatums horen bij het
paar en zijn in die rijen gelijk. Zijn ze dat niet, dan geeft de tool geen datums: geen gok welke rij geldt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

import pandas as pd

from data import instellingen

from . import store
from .catalog import documentatie_url
from .duo import get_duo_data
from .geslacht_opleiding import CODE, NAAM, Opleiding, kies_uit, zoek

DATASET = "overzicht-erkenningen-ho"
BESTAND = 0  # HO_Erkenningen_RIO; 1 is de toelichting (pdf), 2 het controlebestand
BRONNAAM = "DUO, Overzicht Erkenningen ho"
LICENTIE = "CC-BY (Creative Commons Naamsvermelding)"
HO = ("hbo", "wo")

INSTELLING = "INSTELLINGSCODE"
CROHO = "ERKENDEOPLEIDINGSCODE"
OPLEIDINGSNAAM = "OPLEIDINGSEENHEID_NAAM"
STATUS = "STATUS"
NIVEAU = "NIVEAU"
VORM = "VORM"
BEGIN_RECORD = "BEGINDATUM_RECORD"
EINDE_RECORD = "EINDDATUM_RECORD"
UITSTELREDEN = "ACCREDITATIE_UITSTELREDEN"
INLEVERDATUM = "ACCREDITATIE_INLEVERDATUM"
ACTUEEL, HISTORISCH = "ACTUEEL", "HISTORISCH"  # en TOEKOMSTIG: een registratie die nog moet ingaan


@dataclass(frozen=True)
class Datumveld:
    sleutel: str  # de naam in het resultaat: wat de datum is, niet de DUO-kolom
    betekenis: str


# De accreditatiedatums, met hun betekenis volgens de DUO-toelichting v1.8. Een lege datum blijft weg uit het resultaat.
DATUMS: dict[str, Datumveld] = {
    "ACCREDITATIE_BESLUITDATUM": Datumveld(
        "besluitdatum", "Datum van het besluit of de melding van de NVAO over de accreditatie."
    ),
    "ACCREDITATIE_BEGINDATUM": Datumveld("begindatum", "Begindatum van de geldigheid van de accreditatie."),
    INLEVERDATUM: Datumveld(
        "uiterste_indiening_volgende_beoordeling",
        "Uiterste datum waarop de instelling het visitatierapport voor de volgende beoordeling bij de NVAO indient. "
        "Geen einddatum: de accreditatie loopt op deze datum niet af. Schrijf nooit 'geaccrediteerd tot' of "
        "'verloopt op' bij deze datum.",
    ),
    "ACCREDITATIE_VOORWAARDENDATUM": Datumveld(
        "uiterste_indiening_voorwaarden",
        "Uiterste datum waarop de instelling met een rapport bij de NVAO aantoont dat aan de voorwaarden is voldaan.",
    ),
    "ACCREDITATIE_UITSTELDATUM": Datumveld(
        "verlengd_tot", "Datum tot wanneer de NVAO of de minister de accreditatie heeft verlengd."
    ),
    "ACCREDITATIE_INTREKKINGSDATUM": Datumveld(
        "intrekking", "Datum waarop het intrekkingsbesluit van de NVAO of de minister in werking treedt."
    ),
    "ACCREDITATIE_AFBOUWDATUM": Datumveld(
        "afbouw", "Uiterste datum tot wanneer zittende studenten de opleiding kunnen afronden."
    ),
    "ACCREDITATIE_VERVALDATUM": Datumveld(
        "vervaldatum_nieuwe_opleiding",
        "Einde van de accreditatietermijn van een nieuwe opleiding. Hoort alleen bij nieuwe opleidingen: noem hem "
        "niet als einddatum van de accreditatie van een bestaande opleiding.",
    ),
}
VERPLICHT = (INSTELLING, CROHO, OPLEIDINGSNAAM, STATUS, NIVEAU, VORM, BEGIN_RECORD, EINDE_RECORD, UITSTELREDEN, *DATUMS)

# NIVEAU volgens de toelichting; een andere waarde is "onbekend", geen gok.
NIVEAUS = {
    "HBO-AD": "hbo associate degree",
    "HBO-BA": "hbo bachelor",
    "HBO-MA": "hbo master",
    "HBO-PM": "hbo postinitiële master",
    "HBO-O": "hbo ongedeeld",
    "WO-BA": "wo bachelor",
    "WO-MA": "wo master",
    "WO-PM": "wo postinitiële master",
    "WO-O": "wo ongedeeld",
}
VORMEN = {"VOLTIJD": "voltijd", "DEELTIJD": "deeltijd", "DUAAL": "duaal"}
# ART_5_16_LID_4: het WHW-artikel waarop de verlenging rust.
_ARTIKEL = re.compile(r"ART_(\d+[A-Z]?)_(\d+[A-Z]?)_LID_(\d+)")

GEEN_OORDEEL = (
    "Dit overzicht van DUO bevat geen oordeel van de NVAO (zoals voldoende, goed of excellent), geen besluittekst en "
    "geen rapport: alleen de datums die DUO over de accreditatie registreert. NVAO-oordelen zitten (nog) niet in deze "
    "app. Noem geen oordeel en leid er geen af."
)
GEEN_RANGLIJST = "De datums zeggen niets over kwaliteit: vergelijk of rangschik opleidingen of instellingen er niet op."


def _leeg(waarde) -> bool:
    return waarde is None or (not isinstance(waarde, str) and pd.isna(waarde)) or not str(waarde).strip()


def croho(waarde) -> str | None:
    """De CROHO-code als tekst van vijf cijfers: 4181, 4181.0 en '04181' zijn '04181'; None zonder code."""
    if isinstance(waarde, bool) or _leeg(waarde):
        return None
    if isinstance(waarde, float) and waarde.is_integer():
        waarde = int(waarde)
    tekst = str(waarde).strip().removesuffix(".0")
    return tekst.zfill(5) if tekst.isdigit() and len(tekst) <= 5 else tekst


def _dag(waarde) -> date | None:
    if _leeg(waarde):
        return None
    try:
        return date.fromisoformat(str(waarde).strip()[:10])
    except ValueError:
        return None


def datum(waarde) -> str | None:
    """Een DUO-datum (2026-05-01) als 01-05-2026; leeg is None, een andere vorm blijft zoals hij is."""
    if (dag := _dag(waarde)) is not None:
        return f"{dag:%d-%m-%Y}"
    return None if _leeg(waarde) else str(waarde).strip()


def uitstelreden(waarde) -> str | None:
    """ART_5_16_LID_4 als 'artikel 5.16 lid 4 WHW'; een andere waarde als DUO-code, niet uitgelegd."""
    if _leeg(waarde):
        return None
    tekst = str(waarde).strip()
    if gevonden := _ARTIKEL.fullmatch(tekst):
        hoofd, nummer, lid = gevonden.groups()
        return f"artikel {hoofd.lower()}.{nummer.lower()} lid {lid} WHW"
    return f"DUO-code {tekst}"


def _laad() -> tuple[pd.DataFrame, store.KeyMeta | None, str] | str:
    """Het erkenningenbestand via get_duo_data, met zijn meta en key; de melding als tekst als dat niet lukt."""
    uit = get_duo_data(DATASET, BESTAND)
    try:
        geladen = json.loads(uit)
    except (TypeError, ValueError):
        return uit
    if not isinstance(geladen, dict) or not isinstance(key := geladen.get("data_key"), str):
        return uit
    df = store.get(key)
    if df is None:
        return f"Het bestand van {BRONNAAM} staat niet meer in het geheugen; probeer het opnieuw."
    if ontbrekend := [k for k in VERPLICHT if k not in df.columns]:
        return (
            f"Het bestand van {BRONNAAM} mist de kolommen {', '.join(ontbrekend)}: DUO veranderde het formaat. Geen "
            "accreditatiedata; noem ze niet."
        )
    return df, store.meta(key), key


def _niveau(waarde) -> str:
    return NIVEAUS.get(str(waarde).strip(), "onbekend")


def _opleidingen(rijen: pd.DataFrame) -> pd.DataFrame:
    """Per CROHO-code de naam en het niveau uit het nieuwste record, in de kolommen van de opleidingsresolutie."""
    nieuwste = rijen.sort_values(BEGIN_RECORD).drop_duplicates(CROHO, keep="last")
    return pd.DataFrame(
        {CODE: nieuwste[CROHO], NAAM: nieuwste[OPLEIDINGSNAAM].astype(str), NIVEAU: nieuwste[NIVEAU].map(_niveau)}
    )


def _gevraagd(opleiding: str) -> str:
    """Een CROHO-code met vijf cijfers, zoals DUO hem schrijft (4181 is 04181); een naam blijft zoals hij is."""
    tekst = " ".join(str(opleiding or "").split())
    return (croho(tekst) or tekst) if tekst.isdigit() else tekst


def _historisch(rijen: pd.DataFrame, huidig: pd.DataFrame, gevraagd: str) -> str | None:
    """De melding als de opleiding alleen nog historisch geregistreerd is; alleen op code of hele naam, geen deel.

    Een deel van een naam ("Verpleegkunde") paste op een oude lerarenopleiding, terwijl de huidige opleiding
    "Opleiding tot Verpleegkundige" heet: dan volgen de voorstellen uit de huidige registraties.
    """
    historisch = rijen[(rijen[STATUS] == HISTORISCH) & ~rijen[CROHO].isin(huidig[CROHO])]
    oud = _opleidingen(historisch)
    precies = oud[(oud[CODE] == gevraagd) | (oud[NAAM].str.lower() == gevraagd.lower())]
    if len(precies) != 1:
        return None
    code, naam = precies[CODE].iloc[0], precies[NAAM].iloc[0]
    einde = datum(historisch.loc[historisch[CROHO] == code, EINDE_RECORD].dropna().max())
    tot = f" (laatste registratie tot {einde})" if einde else ""
    return (
        f"{naam} ({code}) staat in {BRONNAAM} alleen nog als historische registratie{tot}: geen actuele erkenning. "
        "Noem geen accreditatiedatums als actueel."
    )


def _kies(rijen: pd.DataFrame, gevraagd: str) -> Opleiding | str:
    """De opleiding onder de huidige registraties, op CROHO-code of naam; de melding als tekst. Geen gok.

    Bij meer treffers noemt de melding ook het niveau: Bedrijfskunde is bij één instelling een bachelor en een
    associate degree, elk met een eigen CROHO-code.
    """
    huidig = rijen[rijen[STATUS] != HISTORISCH]
    opleidingen = _opleidingen(huidig)
    gevonden = zoek(opleidingen, gevraagd)
    if len(gevonden) > 1:
        keuzes = "; ".join(f"{naam}, {niveau} ({code})" for code, naam, niveau in gevonden.itertuples(index=False))
        return f"Meer opleidingen passen bij {gevraagd!r}: {keuzes}. Geef de CROHO-code van de bedoelde."
    if gevonden.empty and (melding := _historisch(rijen, huidig, gevraagd)):
        return melding
    return kies_uit(opleidingen, gevraagd)


def _datums(paar: pd.DataFrame) -> dict | None:
    """De accreditatiedatums van het paar met hun betekenis; None als de rijen elkaar tegenspreken."""
    kolommen = [*DATUMS, UITSTELREDEN]
    uniek = paar[kolommen].drop_duplicates()
    if len(uniek) != 1:
        return None
    rij = uniek.iloc[0]
    uit: dict[str, dict[str, str | None]] = {
        v.sleutel: {"datum": d, "betekenis": v.betekenis} for k, v in DATUMS.items() if (d := datum(rij[k]))
    }
    if reden := uitstelreden(rij[UITSTELREDEN]):
        # Een grond zonder datum komt ook voor (78 actuele rijen op 30-10): dan staat de grond er alleen bij.
        verlengd = uit.get("verlengd_tot") or {
            "datum": None,
            "betekenis": DATUMS["ACCREDITATIE_UITSTELDATUM"].betekenis,
        }
        uit["verlengd_tot"] = {**verlengd, "grond": reden}
    return uit


def _erkenning(paar: pd.DataFrame) -> str:
    """Wat de registratie van het paar zegt: actueel erkend, of pas vanaf een datum."""
    if (paar[STATUS] == ACTUEEL).any():
        return "De opleiding staat op het peilmoment als actuele OCW-erkende opleiding in het overzicht."
    vanaf = datum(paar[BEGIN_RECORD].min())
    return (
        "De opleiding staat alleen als toekomstige registratie in het overzicht"
        + (f", vanaf {vanaf}" if vanaf else "")
        + "; nog niet als actuele erkenning."
    )


def _noten(paar: pd.DataFrame, vandaag: date) -> list[str]:
    """De vaste noten: geen ranglijst, en een uiterste indiening in het verleden is geen verlopen accreditatie."""
    noten = [GEEN_RANGLIJST]
    dag = _dag(paar[INLEVERDATUM].iloc[0])
    if dag is not None and dag < vandaag:
        noten.append(
            f"De uiterste indiening voor de volgende beoordeling ({dag:%d-%m-%Y}) ligt vóór vandaag. Dat betekent niet "
            "dat de accreditatie is verlopen: de beoordeling kan lopen of verlengd zijn. Trek er geen conclusie uit "
            "over de status."
        )
    return noten


def _uitkomst(
    profiel: dict, opl: Opleiding, paar: pd.DataFrame, meta: store.KeyMeta | None, key: str, vandaag: date
) -> dict | str:
    datums = _datums(paar)
    if datums is None:
        return (
            f"{BRONNAAM} geeft voor {opl.naam} ({opl.code}) bij {profiel['naam']} verschillende accreditatiedatums per "
            "vestiging of vorm. Geen eenduidige datums; noem ze niet."
        )
    niveaus = sorted({_niveau(n) for n in paar[NIVEAU].dropna()})
    vormen = sorted({VORMEN.get(str(v).strip().upper(), "onbekend") for v in paar[VORM].dropna()})
    bron = {"naam": BRONNAAM, "url": documentatie_url(DATASET), "licentie": LICENTIE, "data_key": key}
    if meta is not None and meta.peilmoment:
        bron["peilmoment"] = meta.peilmoment
    return {
        "instelling": {"naam": profiel["naam"], "instellingscode": profiel["instellingscode"]},
        "opleiding": {"croho": opl.code, "naam": opl.naam, "niveau": niveaus, "vormen": vormen},
        "erkenning": _erkenning(paar),
        "datums": datums,
        "geen_oordeel": GEEN_OORDEEL,
        "noot": " ".join(_noten(paar, vandaag)),
        "bron": bron,
    }


def get_accreditatie(instelling: str, opleiding: str) -> str:
    """De accreditatiedatums van één hbo- of wo-opleiding bij één instelling, met betekenis en bron (#726)."""
    profiel = instellingen.instellingsprofiel(str(instelling or ""))
    if profiel is None:
        return (
            f"Onbekende instelling {instelling!r}: het register kent deze naam of alias niet. Geen gok; controleer de "
            "naam, bijvoorbeeld met get_rio_instelling."
        )
    if profiel.get("sector") not in HO:
        return (
            f"{profiel['naam']} is een {profiel.get('sector')}-instelling. Accreditatie door de NVAO geldt voor hbo- en "
            "wo-opleidingen; voor het oordeel van de Inspectie over een mbo-bestuur is er get_inspectieoordeel."
        )
    if not (gevraagd := _gevraagd(opleiding)):
        return "Geef de opleiding: haar naam of CROHO-code."
    geladen = _laad()
    if isinstance(geladen, str):
        return geladen
    df, meta, key = geladen
    rijen = df[df[INSTELLING].astype(str).str.strip() == profiel["instellingscode"]]
    rijen = rijen.assign(**{CROHO: rijen[CROHO].map(croho)})
    if rijen.empty:
        return (
            f"{profiel['naam']} ({profiel['instellingscode']}) staat niet in {BRONNAAM}. Noem geen accreditatiedatums."
        )
    opl = _kies(rijen, gevraagd)
    if isinstance(opl, str):
        return f"{opl} (instelling {profiel['naam']}, {BRONNAAM})"
    huidig = rijen[(rijen[CROHO] == opl.code) & (rijen[STATUS] != HISTORISCH)]
    paar = huidig[huidig[STATUS] == ACTUEEL] if (huidig[STATUS] == ACTUEEL).any() else huidig
    uit = _uitkomst(profiel, opl, paar, meta, key, date.today())
    return uit if isinstance(uit, str) else json.dumps(uit, ensure_ascii=False, separators=(",", ":"))

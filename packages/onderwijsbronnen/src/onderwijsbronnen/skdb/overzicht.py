"""Overzichten uit één SKDB-export: dezelfde rijen voor de chat (tools/studiekeuze.py) en voor een snippet (#957).

Elke functie neemt een `Export` en geeft een lijst rijen (dicts) in een vaste volgorde, met vaste afronding; er wordt
niets geschat of aangevuld. Een leeg veld in de bron blijft `None`. De sleutels naar andere bronnen staan in elke rij:
`brin` (= RIO/DUO-instellingscode), `croho` (= RIO/DUO-opleidingscode) en `studiecode` (de landelijke studie van LCSK,
meestal gelijk aan de CROHO-code, niet altijd: samengevoegde studies).

- `opleidingen`: per opleiding van een instelling en per vorm (voltijd/deeltijd/duaal): NSE-oordeel naast het
  landelijke oordeel van dezelfde studie, doorstroom naar jaar 2, diplomarendement en numerus fixus;
- `studie`: per landelijke studie en vorm: NSE, rendement, aantal aanbieders, het ROA-opleidingstype en de
  arbeidsmarkt van de SOI-rubriek;
- `toelating`: de wettelijke vooropleidingseisen (havo, vwo, mbo) per opleiding;

Wat een andere bron al leidend heeft, staat hier niet (afspraken #878): aantallen studenten en eerstejaars (DUO telt
anders en heeft de reeks), wettelijk collegegeld (de wettekst), accreditatie (DUO/NVAO) en de aansluiting
studie-baan (ROA-AIS, nieuwere editie). De ruwe tabellen blijven met `load`/`Export.frame` te lezen.
- `numerus_fixus`: opleidingen met loting of decentrale selectie, met capaciteit;
- `doorstroom_mbo_hbo` en `doorstroom_bachelor_master`: waar gediplomeerden naartoe gaan.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .export import Export

VORMEN = {1: "voltijd", 2: "deeltijd", 3: "duaal"}
SORTERINGEN = ("naam", "oordeel", "doorstroom_jaar2")
GRADEN = {"bachelor": "Bachelor", "master": "Master", "associate degree": "Associate degree", "ad": "Associate degree"}

# NSE-thema's (gemiddelde op 1–5) per opleidingsvorm, met de naam in de uitkomst.
NSE_THEMAS = {
    "inhoudOpzetGewogenGemiddelde": "nse_inhoud_opzet",
    "docentenGewogenGemiddelde": "nse_docenten",
    "toetsingBeoordelingGewogenGemiddelde": "nse_toetsing",
    "studieBegeleidingGewogenGemiddelde": "nse_begeleiding",
    "betrokkenheidContactGewogenGemiddelde": "nse_betrokkenheid",
    "aansluitingBeroepGewogenGemiddelde": "nse_aansluiting_beroep",
    "studieFaciliteitenGewogenGemiddelde": "nse_faciliteiten",
    "sfeerGewogenGemiddelde": "nse_sfeer",
    "opnieuwKiezenGewogenGemiddelde": "nse_opnieuw_kiezen",
    "studieDrukGewogenGemiddelde": "nse_studiedruk",
}
# Arbeidsmarkt van afgestudeerden per SOI-rubriek × hbo/wo × graad × vorm.
ARBEIDSMARKT = {
    "rubriekNaam": "soi_rubriek",
    "maandSalarisMediaan": "salaris_mediaan_bruto_maand",
    "werkloosPerc": "werkloos_pct",
    "baanOpNiveauPerc": "baan_op_niveau_pct",
    "baanInVakgebiedPerc": "baan_in_vakgebied_pct",
    "vastContractPerc": "vast_contract_pct",
    "duurTotSubstantieleBaanMaanden": "maanden_tot_substantiele_baan",
    "achterafZelfdeStudieKeuzePerc": "achteraf_zelfde_keuze_pct",
}


def _getal(waarde, decimalen: int = 1):
    """Een getal afgerond, een geheel getal als geheel getal; leeg of geen getal blijft None."""
    if isinstance(waarde, bool) or waarde is None:
        return None
    if isinstance(waarde, int):
        return waarde
    if isinstance(waarde, float):
        return round(waarde, decimalen)
    return None


def _code(waarde) -> int | None:
    try:
        return int(str(waarde).strip())
    except (TypeError, ValueError):
        return None


def _vorm(waarde: str | None) -> str | None:
    """'Voltijd' → 'voltijd'; None blijft None."""
    return str(waarde).strip().lower() if waarde else None


def _plaats(waarde: str | None) -> str | None:
    """'LEEUWARDEN' → 'Leeuwarden', "'S-HERTOGENBOSCH" → "'s-Hertogenbosch"."""
    if not waarde:
        return None
    tekst = str(waarde).strip().title()
    return tekst.replace("'S-", "'s-")


def _bevat(tekst: str | None, zoek: str) -> bool:
    """Of de tekst de zoekterm bevat aan het begin van een woord: "ict" vindt "ICT" en "HBO-ICT", niet "Conflict"
    (#960). Geen woordteken ervoor, in plaats van `\\b`, zodat ook "'s-hertogenbosch" aan het begin past."""
    return bool(tekst) and re.search(r"(?<!\w)" + re.escape(zoek), str(tekst).lower()) is not None


def _per(rijen: Iterable[dict], *sleutels: str) -> dict:
    return {tuple(r.get(s) for s in sleutels): r for r in rijen}


def jaren(export: Export) -> dict[str, int | None]:
    """Het NSE-jaar (`enqueteJaar`) en het 1cijferHO-jaar (`eenCijferHoMeestRecenteJaar`, begin van het collegejaar)
    van de export: de hoogste waarde in `opleidingvormen`, None als het veld overal leeg is."""
    rijen = export.rijen("opleidingvormen")

    def hoogste(veld: str) -> int | None:
        return max((v for r in rijen if isinstance(v := r.get(veld), int)), default=None)

    return {"nse": hoogste("enqueteJaar"), "1cijferho": hoogste("eenCijferHoMeestRecenteJaar")}


def instellingen(export: Export) -> list[dict]:
    """De instellingen van de export: BRIN, naam, soort (hogeschool/universiteit) en bekostiging."""
    return sorted(
        (
            {
                "brin": r.get("instellingCode"),
                "naam": r.get("instellingNaam"),
                "soort": r.get("instellingSoort"),
                "bekostiging": r.get("instellingBekostiging"),
            }
            for r in export.rijen("instellingen")
        ),
        key=lambda r: str(r["naam"]),
    )


def _filter_opleiding(
    r: dict, brin: str | None, croho: int | None, naam: str | None, soort_ho: str | None, graad: str | None
) -> bool:
    if brin and r.get("instellingCode") != brin:
        return False
    if croho is not None and croho not in (_code(r.get("opleidingCode")), _code(r.get("studieOpleidingCodeSkdb"))):
        return False
    if naam and not any(_bevat(r.get(k), naam) for k in ("opleidingNaam", "rioNaam", "hoviOpleidingNaam")):
        return False
    if soort_ho and str(r.get("soortHo", "")).upper() != soort_ho.upper():
        return False
    return not (graad and r.get("graad") != GRADEN.get(graad.lower(), graad))


def _numerus_fixus_per_opleiding(export: Export) -> dict[tuple, dict]:
    """(BRIN, CROHO, vorm) → capaciteit en studiejaar van het nieuwste studiejaar, opgeteld over de taaltrajecten."""
    nieuwste: dict[tuple, dict] = {}
    for r in export.rijen("lotingopleidingendecentraleselecties"):
        sleutel = (r.get("instellingCode"), _code(r.get("opleidingCode")), _vorm(r.get("opleidingVorm")))
        jaar, capaciteit = r.get("studieJaar"), r.get("capaciteit")
        huidig = nieuwste.get(sleutel)
        if huidig is None or (jaar or 0) > huidig["studiejaar"]:
            nieuwste[sleutel] = {"studiejaar": jaar or 0, "capaciteit": capaciteit or 0}
        elif jaar == huidig["studiejaar"]:
            huidig["capaciteit"] += capaciteit or 0
    return nieuwste


def _sorteer(rijen: list[dict], sorteer: str, naamvelden: tuple[str, ...]) -> list[dict]:
    """Op naam (standaard), of aflopend op een maat met lege waarden achteraan; gelijke waarden op naam."""
    rijen.sort(key=lambda r: tuple(str(r.get(v) or "") for v in naamvelden))
    veld = {
        "oordeel": "nse_oordeel",
        "doorstroom_jaar2": "doorstroom_jaar2_pct",
    }.get(sorteer)
    if veld:
        rijen.sort(key=lambda r: (r.get(veld) is None, -(r.get(veld) or 0)))
    return rijen


def opleidingen(
    export: Export,
    *,
    brin: str | None = None,
    croho: int | None = None,
    naam: str | None = None,
    soort_ho: str | None = None,
    graad: str | None = None,
    vorm: str | None = None,
    plaats: str | None = None,
    alleen_numerus_fixus: bool = False,
    sorteer: str = "naam",
    themas: bool = True,
) -> list[dict]:
    """Per opleiding (instelling × CROHO × vestiging) en per vorm de kerncijfers, met het landelijke NSE-oordeel van
    dezelfde studie en vorm ernaast. Filters zijn optioneel en sluiten elkaar in (EN)."""
    zoek = naam.lower().strip() if naam else None
    vorm = _vorm(vorm)
    plaats_zoek = plaats.lower().strip() if plaats else None
    namen = {r.get("instellingCode"): r.get("instellingNaam") for r in export.rijen("instellingen")}
    opleidingen_per_id = {
        r.get("opleidingSkdb"): r
        for r in export.rijen("opleidingen")
        if _filter_opleiding(r, brin, croho, zoek, soort_ho, graad)
        and (not plaats_zoek or _bevat(r.get("bezoekAdresStad"), plaats_zoek))
    }
    landelijk = _per(export.rijen("studievormen"), "studieOpleidingCodeSkdb", "studieVormId")
    fixus = _numerus_fixus_per_opleiding(export)
    rijen = []
    for v in export.rijen("opleidingvormen"):
        o = opleidingen_per_id.get(v.get("opleidingSkdb"))
        if o is None or (vorm and _vorm(v.get("opleidingVorm")) != vorm):
            continue
        code, vorm_id, v_naam = _code(o.get("opleidingCode")), v.get("opleidingVormId"), _vorm(v.get("opleidingVorm"))
        nf = fixus.get((o.get("instellingCode"), code, v_naam))
        if alleen_numerus_fixus and nf is None:
            continue
        land = landelijk.get((o.get("studieOpleidingCodeSkdb"), vorm_id)) or {}
        rij = {
            "instelling": namen.get(o.get("instellingCode")),
            "brin": o.get("instellingCode"),
            "opleiding": o.get("opleidingNaam"),
            "croho": code,
            "studiecode": _code(o.get("studieOpleidingCodeSkdb")),
            "graad": o.get("graad"),
            "soort_ho": o.get("soortHo"),
            "vorm": v_naam,
            "plaats": _plaats(o.get("bezoekAdresStad")),
            "bekostigd": o.get("opleidingBekostiging") == "Bekostigd",
            "nse_oordeel": _getal(v.get("algemeenOordeelGewogenGemiddelde"), 2),
            "nse_respondenten": _getal(v.get("algemeenOordeelAantal")),
            "nse_oordeel_landelijk": _getal(land.get("algemeenOordeelGewogenGemiddelde"), 2),
            "doorstroom_jaar2_pct": _getal(v.get("doorstroomJaar2Perc")),
            "diploma_opleiding_pct": _getal(v.get("opleidingDiplomasPerc")),
            "numerus_fixus_capaciteit": nf["capaciteit"] if nf else None,
            "numerus_fixus_studiejaar": nf["studiejaar"] if nf else None,
        }
        if themas:
            rij.update({uit: _getal(v.get(veld), 2) for veld, uit in NSE_THEMAS.items()})
        rijen.append(rij)
    return _sorteer(rijen, sorteer, ("instelling", "opleiding", "plaats", "vorm"))


def zoek_studies(export: Export, tekst: str, *, soort_ho: str | None = None, graad: str | None = None) -> list[dict]:
    """Landelijke studies met een woord in de naam dat met de tekst begint (of met die code), op naam; om één studie te kiezen."""
    zoek = str(tekst).lower().strip()
    code = _code(zoek)
    uit = []
    for r in export.rijen("studies"):
        if soort_ho and str(r.get("soortHo", "")).upper() != soort_ho.upper():
            continue
        if graad and r.get("graad") != GRADEN.get(graad.lower(), graad):
            continue
        if (code is not None and _code(r.get("studieOpleidingCodeSkdb")) == code) or (
            code is None and _bevat(r.get("studieNaam"), zoek)
        ):
            uit.append(
                {
                    "studie": r.get("studieNaam"),
                    "studiecode": _code(r.get("studieOpleidingCodeSkdb")),
                    "graad": r.get("graad"),
                    "soort_ho": r.get("soortHo"),
                }
            )
    return sorted(uit, key=lambda r: (str(r["studie"]), str(r["soort_ho"]), str(r["graad"])))


def studie(export: Export, studiecode: int) -> list[dict]:
    """Eén landelijke studie per vorm: NSE, rendement, aantal aanbieders, het ROA-opleidingstype (de sleutel naar de
    ROA-cijfers) en de arbeidsmarkt van haar SOI-rubriek (per rubriek, niet per studie)."""
    studies = {_code(r.get("studieOpleidingCodeSkdb")): r for r in export.rijen("studies")}
    s = studies.get(studiecode)
    if s is None:
        return []
    soi = _per(export.rijen("standaardonderwijsindelingvorm"), "soiId", "studieVormId")
    aanbieders: dict[int, set] = {}
    for v in export.rijen("opleidingvormen"):
        if _code(v.get("studieOpleidingCodeSkdb")) == studiecode:
            aanbieders.setdefault(v.get("opleidingVormId"), set()).add(v.get("opleidingSkdb"))
    rijen = []
    for v in export.rijen("studievormen"):
        if _code(v.get("studieOpleidingCodeSkdb")) != studiecode:
            continue
        vorm_id = v.get("studieVormId")
        soi_id = f"{v.get('rubriekCode')}-{v.get('soortHo')}-{v.get('graad')}" if v.get("rubriekCode") else None
        markt = soi.get((soi_id, vorm_id)) or {}
        rij = {
            "studie": s.get("studieNaam"),
            "studiecode": studiecode,
            "graad": v.get("graad"),
            "soort_ho": v.get("soortHo"),
            "vorm": _vorm(v.get("studieVorm")) or VORMEN.get(vorm_id),
            "aantal_opleidingen": len(aanbieders.get(vorm_id, ())),
            "nse_oordeel": _getal(v.get("algemeenOordeelGewogenGemiddelde"), 2),
            "nse_respondenten": _getal(v.get("algemeenOordeelAantal")),
            "doorstroom_jaar2_pct": _getal(v.get("doorstroomJaar2Perc")),
            "diploma_opleiding_pct": _getal(v.get("opleidingDiplomasPerc")),
            "roa_opleidingstype": s.get("opleidingType"),
            **{
                uit: (markt.get(veld) if uit == "soi_rubriek" else _getal(markt.get(veld)))
                for veld, uit in ARBEIDSMARKT.items()
            },
        }
        rijen.append(rij)
    return sorted(rijen, key=lambda r: list(VORMEN.values()).index(r["vorm"]) if r["vorm"] in VORMEN.values() else 9)


# De wettelijke vooropleidingseisen (RATHO) per opleiding, met de naam in de uitkomst.
TOELATING = {
    "wettelijkeVooropleidingEisenHavo": "havo",
    "wettelijkeVooropleidingEisenVwo": "vwo",
    "toelatingsEisenMbo": "mbo",
    "wettelijkeAanvullendeEisenHavo": "aanvullend_havo",
    "wettelijkeAanvullendeEisenVwo": "aanvullend_vwo",
}


def toelating(
    export: Export,
    *,
    brin: str | None = None,
    croho: int | None = None,
    naam: str | None = None,
    soort_ho: str | None = None,
    graad: str | None = None,
) -> list[dict]:
    """De vooropleidingseisen per opleiding (CROHO), één rij per gelijke set eisen met de instellingen die haar hebben:
    meestal één rij per opleiding, twee als één instelling (bijv. de Open Universiteit) andere eisen noemt."""
    zoek = naam.lower().strip() if naam else None
    namen = {r.get("instellingCode"): r.get("instellingNaam") for r in export.rijen("instellingen")}
    # Een naam kiest opleidingen (CROHO-codes), niet vestigingsrijen: elke instelling noemt haar opleiding anders
    # ("Verpleegkunde", "Opleiding tot Verpleegkundige"), en de lijst instellingen hoort bij de code, niet bij de naam.
    codes = (
        {
            _code(o.get("opleidingCode"))
            for o in export.rijen("opleidingen")
            if _filter_opleiding(o, None, None, zoek, None, None)
        }
        if zoek
        else None
    )
    groepen: dict[tuple, dict] = {}
    for o in export.rijen("opleidingen"):
        if not _filter_opleiding(o, brin, croho, None, soort_ho, graad):
            continue
        if codes is not None and _code(o.get("opleidingCode")) not in codes:
            continue
        eisen = tuple(o.get(veld) for veld in TOELATING)
        sleutel = (_code(o.get("opleidingCode")), eisen)
        rij = groepen.setdefault(
            sleutel,
            {
                "opleiding": o.get("rioNaam") or o.get("opleidingNaam"),
                "croho": _code(o.get("opleidingCode")),
                "graad": o.get("graad"),
                "soort_ho": o.get("soortHo"),
                **dict(zip(TOELATING.values(), eisen, strict=True)),
                "instellingen": set(),
            },
        )
        rij["instellingen"].add(namen.get(o.get("instellingCode")) or o.get("instellingCode"))
    # De instellingen als tekst: een tabelcel in de store en een CSV-export, niet een lijst.
    rijen = [
        {
            **r,
            "aantal_instellingen": len(r["instellingen"]),
            "instellingen": "; ".join(sorted(map(str, r["instellingen"]))),
        }
        for r in groepen.values()
    ]
    return sorted(rijen, key=lambda r: (str(r["opleiding"]), r["croho"] or 0, -r["aantal_instellingen"]))


def numerus_fixus(
    export: Export, *, brin: str | None = None, croho: int | None = None, naam: str | None = None
) -> list[dict]:
    """Opleidingen met loting of decentrale selectie: capaciteit per taaltraject, studiejaar en aanmelddatum."""
    zoek = naam.lower().strip() if naam else None
    namen = {r.get("instellingCode"): r.get("instellingNaam") for r in export.rijen("instellingen")}
    rijen = [
        {
            "instelling": namen.get(r.get("instellingCode")),
            "brin": r.get("instellingCode"),
            "opleiding": r.get("opleidingNaam"),
            "croho": _code(r.get("opleidingCode")),
            "vorm": _vorm(r.get("opleidingVorm")),
            "voertaal": r.get("voerTaal"),
            "studiejaar": r.get("studieJaar"),
            "capaciteit": r.get("capaciteit"),
            "keren_meedoen": r.get("kerenMeedoenAantal"),
            "aanmelden_uiterlijk": r.get("aanmeldDatumUiterlijk"),
            "url": r.get("lotingUrl"),
        }
        for r in export.rijen("lotingopleidingendecentraleselecties")
        if (not brin or r.get("instellingCode") == brin)
        and (croho is None or _code(r.get("opleidingCode")) == croho)
        and (not zoek or _bevat(r.get("opleidingNaam"), zoek))
    ]
    return sorted(
        rijen,
        key=lambda r: (
            str(r["instelling"]),
            str(r["opleiding"]),
            str(r["vorm"]),
            r["studiejaar"] or 0,
            str(r["voertaal"]),
        ),
    )


def doorstroom_mbo_hbo(export: Export, *, mbo: str | None = None, studiecode: int | None = None) -> list[dict]:
    """Doorstroom van mbo-4-gediplomeerden naar hbo-studies: per mbo-kwalificatie (beroep_id) de hbo-studies op rang."""
    zoek = mbo.lower().strip() if mbo else None
    rijen = [
        {
            "mbo_opleiding": r.get("mboNaam"),
            "mbo_kwalificatie_id": r.get("mboKwalificatieId"),
            "hbo_studie": r.get("studieNaam"),
            "studiecode": _code(r.get("studieOpleidingCodeSkdb")),
            "graad": r.get("graad"),
            "afgestudeerden_mbo": r.get("afgestudeerdenMboAantal"),
            "doorstromers": r.get("doorstroomMboHboAantal"),
            "doorstroom_pct": _getal(r.get("doorstroomMboHboPerc")),
            "rang": r.get("doorstroomMboHboRang"),
        }
        for r in export.rijen("doorstroommbohbo")
        if (not zoek or _bevat(r.get("mboNaam"), zoek) or str(r.get("mboKwalificatieId", "")).lower() == zoek)
        and (studiecode is None or _code(r.get("studieOpleidingCodeSkdb")) == studiecode)
    ]
    return sorted(rijen, key=lambda r: (str(r["mbo_opleiding"]), r["rang"] or 0, str(r["hbo_studie"])))


def doorstroom_bachelor_master(export: Export, studiecode: int) -> list[dict]:
    """Waar afgestudeerden van een bachelorstudie naartoe gaan: de masters op rang, met aantal en percentage."""
    studies = {_code(r.get("studieOpleidingCodeSkdb")): r.get("studieNaam") for r in export.rijen("studies")}
    rijen = [
        {
            "bachelor": studies.get(studiecode),
            "studiecode": studiecode,
            "master": r.get("masterNaam"),
            "master_studiecode": _code(r.get("masterStudieOpleidingCodeSkdb")),
            "master_croho": _code(r.get("masterOpleidingCode")),
            "doorstromers": r.get("doorstroomBachelorMasterAantal"),
            "doorstroom_pct": _getal(r.get("doorstroomBachelorMasterPerc")),
            "rang": r.get("doorstroomBachelorMasterRang"),
        }
        for r in export.rijen("doorstroombachelormaster")
        if _code(r.get("bachelorStudieOpleidingCodeSkdb")) == studiecode
    ]
    return sorted(rijen, key=lambda r: (r["rang"] or 0, str(r["master"])))

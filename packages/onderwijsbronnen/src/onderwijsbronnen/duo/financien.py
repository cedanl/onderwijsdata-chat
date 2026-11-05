"""Financiële kengetallen en rijksbijdragen per bestuur, uit DUO's verantwoording uit XBRL (#935, besluit #725).

    from onderwijsbronnen.duo import financien

    f = financien.laad()                       # de nieuwste editie, alleen mbo, hbo en wo
    rijen = financien.overzicht(f, "40597")    # per eenheid en verslagjaar: kengetallen, sectorcijfer, signalering

DUO publiceert elk jaar (september/oktober) de jaarrekeningen van alle besturen als open xlsx, elk onderdeel in twee
varianten. Wat hier staat en waarom:

- **Editie.** De verslagjaren staan in de bestandsnaam (`16.-financiele-kengetallen-2021-2025-standaard.xlsx`): een
  vaste link naar de nieuwste editie bestaat niet. De code leest de pagina, kiest per onderdeel het nieuwste bestand en
  eist dat alle onderdelen uit dezelfde editie komen. Een vervallen bestand geeft bij DUO HTTP 200 met een HTML-pagina
  (soft 404): alleen een antwoord dat geen tekst is en met de zip-handtekening begint, telt als bestand.
- **Variant `standaard`**: geconsolideerd waar het bestuur dat aanleverde, anders enkelvoudig. De variant staat per
  rij; een reeks kan wisselen (13 van 111 reeksen in 2021-2025). Varianten worden nooit gemengd of opgeteld.
- **Alleen mbo, hbo en wo** (`SECTOREN`). DUO rekent een bestuur met meer sectoren toe aan één leidende sector; het
  cijfer geldt altijd voor het hele bestuur.
- **Eenheid.** Een bestuur, behalve 40833: dat heeft drie verantwoordingen, één per BRIN (`40833-25LR`, `-25PZ`,
  `-30RM`), die aparte eenheden blijven (`Bestuurssleutel`).
- **Leeg is geen nul.** Een lege cel is `None`. Weerstandsvermogen, kapitalisatiefactor en netto werkkapitaal zijn
  voor mbo, hbo en wo altijd leeg en worden niet gelezen.
- **Sectorcijfer** volgens de Inspectie (technisch rapport financiële kwaliteit): gewogen, de som van de teller over
  alle eenheden van de sector gedeeld door de som van de noemer. Geen mediaan. Daarvoor leest de code ook de balans en
  de staat van baten en lasten; die posten zelf zijn geen uitkomst. Nagerekend op de editie 2021-2025: mbo 2021
  liquiditeit 1,58, solvabiliteit II 0,64 en rentabiliteit 4,05 %, zoals in het rapport.
- **Signaleringswaarden** van de Inspectie als vaste waarden met bron en jaar: solvabiliteit II onder 0,30 en
  liquiditeit onder een grens die van de totale baten afhangt. Voor rentabiliteit is er geen signaleringswaarde.

De openpyxl-lezer leest in read-only-modus, en de bestanden geven een te kleine bladdimensie op (rijksbijdragen
`A1:N` bij 15 kolommen): zonder `reset_dimensions()` vallen de laatste kolommen stil weg.
"""

from __future__ import annotations

import io
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import httpx

from .._kern.bestuur import Bestuurssleutel

BASIS = "https://duo.nl"
PAGINA = f"{BASIS}/open_onderwijsdata/onderwijs-algemeen/financiele-overzichten/financiele-verantwoording-uit-xbrl.jsp"
TITEL = "Financiële verantwoording uit XBRL"
VARIANT = "standaard"
SECTOREN = ("MBO", "HBO", "WO")
_HEADERS = {"User-Agent": "onderwijsbronnen (https://github.com/cedanl/onderwijsdata-chat)"}
_TIMEOUT_S = 60

# Per onderdeel het nummer en de naam in de bestandsnaam, en de kolommen die de code leest (veld → kolomkop).
ONDERDELEN: dict[str, tuple[int, str]] = {
    "kengetallen": (16, "financiele-kengetallen"),
    "rijksbijdragen": (12, "rijksbijdragen"),
    "balans": (1, "balans"),
    "baten_en_lasten": (2, "staat-van-baten-en-lasten"),
}
KOLOMMEN: dict[str, dict[str, str]] = {
    "kengetallen": {
        "solvabiliteit_1": "Solvabiliteit I",
        "solvabiliteit_2": "Solvabiliteit II",
        "liquiditeit": "Liquiditeit (current ratio)",
        "rentabiliteit": "Rentabiliteit",
    },
    "rijksbijdragen": {
        # Het totaal is zonder de werkplaatsfunctie (umc): nagerekend op alle 90 wo-rijen van 2021-2025.
        "rijksbijdragen": "Totaal van rijksbijdragen",
        "werkplaatsfunctie": "Rijksbijdrage voor de werkplaatsfunctie (universiteit met universitair medisch centrum)",
    },
    "balans": {
        "eigen_vermogen": "Eigen vermogen",
        "voorzieningen": "Voorzieningen",
        "totaal_passiva": "Totaal van passiva",
        "vlottende_activa": "Totaal van vlottende activa",
        "kortlopende_schulden": "Kortlopende schulden",
    },
    "baten_en_lasten": {
        "baten": "Totaal van baten",
        "financiele_baten": "Financiële baten",
        "resultaat": "Totaal van resultaat voor belastingen",
    },
}
_SLEUTELKOLOMMEN = ("Bevoegd Gezag", "Sector", "Groepering", "Naam", "Verslagjaar", "Geconsolideerd of enkelvoudig")
_VARIANTEN = {"geconsolideerd": "geconsolideerd", "enkelvoudig": "enkelvoudig"}

# Na de link volgen in dezelfde tabelrij de cellen peildatum en publicatiedatum ("31 december 2025").
_CEL = re.compile(r"<td[^>]*>\s*([^<]*?)\s*</td>")
_DATUM = re.compile(r"\d{1,2} [a-z]+ 20\d{2}")
_RIJBREEDTE = 400


class FinancienOnbereikbaar(RuntimeError):
    """De pagina of een bestand is niet op te halen: een HTTP-fout, of een soft 404 (HTML in plaats van xlsx)."""


class FinancienAfwijkend(RuntimeError):
    """De pagina of een bestand wijkt af van de bekende opbouw: de code weigert in plaats van te gokken."""


@dataclass(frozen=True)
class Editie:
    eerste_jaar: int
    laatste_jaar: int
    peildatum: str | None  # zoals DUO hem schrijft: 31 december 2025
    publicatiedatum: str | None  # 15 september 2026
    urls: dict[str, str]  # onderdeel → URL

    @property
    def jaren(self) -> str:
        return f"{self.eerste_jaar}-{self.laatste_jaar}"


@dataclass(frozen=True)
class Bestuursjaar:
    """Eén verslagjaar van één eenheid (bestuur, of een BRIN van 40833)."""

    sleutel: Bestuurssleutel
    naam: str
    sector: str  # MBO, HBO of WO, zoals DUO het bestuur toerekent
    groepering: str  # ROC, BER, HBO, KUNS, PABO, UNIV, TECH, LEVE
    verslagjaar: int
    variant: str  # geconsolideerd of enkelvoudig
    waarden: dict[str, float | None]  # elk veld uit KOLOMMEN; None = leeg in de bron


@dataclass(frozen=True)
class Kengetal:
    sleutel: str
    naam: str
    definitie: str
    teller: tuple[str, ...]
    noemer: tuple[str, ...]


# De definities van DUO (definities-kengetallen.pdf), nagerekend uit balans en staat van baten en lasten (540/540
# bestuursjaren mbo/hbo/wo, #725). Teller en noemer zijn ook de basis van het gewogen sectorcijfer.
KENGETALLEN = (
    Kengetal("solvabiliteit_1", "Solvabiliteit I", "eigen vermogen / totaal passiva", ("eigen_vermogen",),
             ("totaal_passiva",)),
    Kengetal("solvabiliteit_2", "Solvabiliteit II", "(eigen vermogen + voorzieningen) / totaal passiva",
             ("eigen_vermogen", "voorzieningen"), ("totaal_passiva",)),
    Kengetal("liquiditeit", "Liquiditeit (current ratio)", "vlottende activa / kortlopende schulden",
             ("vlottende_activa",), ("kortlopende_schulden",)),
    Kengetal("rentabiliteit", "Rentabiliteit", "resultaat vóór belastingen / (totaal baten + financiële baten)",
             ("resultaat",), ("baten", "financiele_baten")),
)
_KENGETAL = {k.sleutel: k for k in KENGETALLEN}
# Een lege post die DUO's eigen kengetal als afwezig behandelt: niet elk bestuur heeft voorzieningen of financiële
# baten. Elke andere lege post houdt de eenheid buiten het sectorcijfer.
_LEEG_IS_AFWEZIG = frozenset({"voorzieningen", "financiele_baten"})

SECTORMETHODE = (
    "Gewogen, volgens de Inspectie van het Onderwijs: de som van de teller over alle eenheden van de sector gedeeld "
    "door de som van de noemer (een eenheid is een bestuur, bij bestuur 40833 elk van de drie verantwoordingen). "
    "Geen mediaan of gemiddelde van de kengetallen zelf."
)

# Signaleringswaarden van de Inspectie (#725, besluit 4). Ze staan niet in een dataset, alleen in het rapport.
SIGNALERINGSWAARDEN_BRON = {
    "naam": "Inspectie van het Onderwijs, Technisch rapport financiële kwaliteit, De Staat van het Onderwijs 2024",
    "jaar": 2024,
    "paragraaf": "3.2.1",
    "url": "https://www.onderwijsinspectie.nl/binaries/onderwijsinspectie/documenten/rapporten/2024/04/17/"
    "technisch-rapport-financiele-kwaliteit/Technisch+rapport+financi%C3%ABle+kwaliteit+-+De+Staat+van+het+Onderwijs"
    "+2024.pdf",
}
SOLVABILITEIT_2_GRENS = 0.30
# De grens voor liquiditeit hangt af van de totale baten (§3.2.1.3): onder € 3 mln 1,50, € 3 tot 12 mln 1,00, boven
# € 12 mln 0,75 en boven € 25 mln 0,50. Een bedrag van precies € 3, 12 of 25 mln valt in de trede "tot en met".
LIQUIDITEIT_TREDEN: tuple[tuple[float, str], ...] = (
    (1.50, "totale baten onder € 3 miljoen"),
    (1.00, "totale baten van € 3 tot en met € 12 miljoen"),
    (0.75, "totale baten boven € 12 tot en met € 25 miljoen"),
    (0.50, "totale baten boven € 25 miljoen"),
)


@dataclass(frozen=True)
class Sectorcijfer:
    sector: str
    verslagjaar: int
    kengetal: str
    waarde: float | None  # None als geen enkele eenheid alle posten heeft, of de noemer 0 is
    eenheden: int  # eenheden in het cijfer
    zonder_posten: int  # eenheden van de sector die buiten het cijfer bleven door een lege post


# ── de pagina en de bestanden ─────────────────────────────────────────────────────────────────────────────────────

Haler = Callable[[str], tuple[bytes, str]]  # URL → (inhoud, content-type)


def _link(nummer: int, naam: str) -> re.Pattern[str]:
    return re.compile(
        rf'href="(/open_onderwijsdata/images/{nummer}\.-{naam}-(20\d\d)-(20\d\d)-{VARIANT}(?:-open-data)?\.xlsx)"'
    )


def lees_editie(pagina: str) -> Editie:
    """De nieuwste editie op de pagina: per onderdeel het bestand van de variant `standaard`, met peil- en
    publicatiedatum uit de tabelrij van de kengetallen. Alle onderdelen moeten uit dezelfde editie komen."""
    gekozen: dict[str, tuple[int, int, str, int]] = {}
    for onderdeel, (nummer, naam) in ONDERDELEN.items():
        treffers = sorted((int(m[3]), int(m[2]), m[1], m.end()) for m in _link(nummer, naam).finditer(pagina))
        if not treffers:
            raise FinancienOnbereikbaar(f"de pagina van DUO noemt geen bestand '{naam}' ({VARIANT})")
        gekozen[onderdeel] = treffers[-1]
    edities = {(eerste, laatste) for laatste, eerste, _, _ in gekozen.values()}
    if len(edities) != 1:
        raise FinancienAfwijkend(f"de onderdelen komen uit verschillende edities: {sorted(edities)}")
    ((eerste, laatste),) = edities
    eind = gekozen["kengetallen"][3]
    cellen = [c for c in _CEL.findall(pagina, eind, eind + _RIJBREEDTE) if _DATUM.fullmatch(c)]
    return Editie(
        eerste_jaar=eerste,
        laatste_jaar=laatste,
        peildatum=cellen[0] if cellen else None,
        publicatiedatum=cellen[1] if len(cellen) > 1 else None,
        urls={o: BASIS + pad for o, (_, _, pad, _) in gekozen.items()},
    )


def xlsx(inhoud: bytes, soort: str, url: str) -> bytes:
    """De inhoud als het een xlsx-bestand is; een HTML-pagina met HTTP 200 (soft 404) is `FinancienOnbereikbaar`."""
    if soort.startswith("text/") or not inhoud.startswith(b"PK"):
        raise FinancienOnbereikbaar(
            f"DUO gaf geen xlsx-bestand maar {soort or 'onbekende inhoud'} voor {url.rsplit('/', 1)[-1]} (soft 404?)"
        )
    return inhoud


def haal(url: str) -> tuple[bytes, str]:
    """De standaard-haler: één GET met timeout en herkenbare naam, redirects gevolgd."""
    antwoord = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT_S, follow_redirects=True)
    antwoord.raise_for_status()
    return antwoord.content, antwoord.headers.get("content-type", "")


def _veilig(haler: Haler, url: str) -> tuple[bytes, str]:
    try:
        return haler(url)
    except httpx.HTTPError as e:
        raise FinancienOnbereikbaar(f"DUO antwoordde niet ({type(e).__name__})") from e


# ── lezen ─────────────────────────────────────────────────────────────────────────────────────────────────────────


def _getal(waarde, kolom: str) -> float | None:
    if waarde is None or (isinstance(waarde, str) and not waarde.strip()):
        return None
    if isinstance(waarde, bool) or not isinstance(waarde, int | float):
        raise FinancienAfwijkend(f"kolom {kolom!r} heeft geen getal maar {waarde!r}")
    return None if math.isnan(waarde) else float(waarde)


def _rijen(inhoud: bytes) -> Iterable[tuple]:
    try:
        import openpyxl
    except ImportError as e:  # pragma: no cover - afhankelijk van de installatie
        raise ImportError("Installeer openpyxl: uv add 'onderwijsbronnen[duo]'") from e
    from openpyxl.utils.exceptions import InvalidFileException
    from zipfile import BadZipFile

    try:
        boek = openpyxl.load_workbook(io.BytesIO(inhoud), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, ValueError, OSError) as e:
        raise FinancienAfwijkend(f"geen leesbaar xlsx-bestand ({type(e).__name__})") from e
    try:
        blad = boek.worksheets[0]
        blad.reset_dimensions()  # de opgegeven dimensie is te klein: anders vallen de laatste kolommen weg
        yield from blad.iter_rows(values_only=True)
    finally:
        boek.close()


def lees_onderdeel(inhoud: bytes, onderdeel: str) -> dict[tuple[str, int], dict]:
    """De rijen van mbo, hbo en wo uit één onderdeel, per (eenheid, verslagjaar).

    Rij 1 is de titel, rij 2 de kop. Een ontbrekende kolom, een onbekende variant, een sleutel die geen bestuursnummer
    is of een dubbele (eenheid, verslagjaar) is `FinancienAfwijkend`.
    """
    rijen = iter(_rijen(inhoud))
    next(rijen, None)
    kop = [str(k).strip() if k is not None else "" for k in next(rijen, ())]
    nodig = (*_SLEUTELKOLOMMEN, *KOLOMMEN[onderdeel].values())
    if ontbreekt := [k for k in nodig if kop.count(k) != 1]:
        raise FinancienAfwijkend(f"{onderdeel}: kolom(men) {ontbreekt} ontbreken of staan er dubbel")
    i = {k: kop.index(k) for k in nodig}
    uit: dict[tuple[str, int], dict] = {}
    for rij in rijen:
        if all(v is None or v == "" for v in rij):
            continue
        rij = (*rij, *[None] * (len(kop) - len(rij)))
        sector = str(rij[i["Sector"]] or "").strip().upper()
        if sector not in SECTOREN:
            continue
        sleutel = Bestuurssleutel.parse(rij[i["Bevoegd Gezag"]])
        jaar = rij[i["Verslagjaar"]]
        variant = _VARIANTEN.get(str(rij[i["Geconsolideerd of enkelvoudig"]] or "").strip().lower())
        if sleutel is None or not isinstance(jaar, int) or variant is None:
            raise FinancienAfwijkend(f"{onderdeel}: onleesbare rij {rij[: len(_SLEUTELKOLOMMEN)]!r}")
        if (str(sleutel), jaar) in uit:
            raise FinancienAfwijkend(f"{onderdeel}: {sleutel} {jaar} staat er twee keer")
        uit[(str(sleutel), jaar)] = {
            "sleutel": sleutel,
            "naam": " ".join(str(rij[i["Naam"]] or "").split()),
            "sector": sector,
            "groepering": str(rij[i["Groepering"]] or "").strip(),
            "verslagjaar": jaar,
            "variant": variant,
            "waarden": {veld: _getal(rij[i[kolom]], kolom) for veld, kolom in KOLOMMEN[onderdeel].items()},
        }
    return uit


def lees(editie: Editie, bestanden: dict[str, bytes]) -> Financien:
    """De eenheden uit de vier onderdelen van één editie, samengevoegd per (eenheid, verslagjaar).

    De kengetallen bepalen welke eenheden er zijn. Sector en variant moeten in elk onderdeel gelijk zijn: anders
    zouden posten uit verschillende varianten in één kengetal of sectorcijfer belanden.
    """
    delen = {onderdeel: lees_onderdeel(bestanden[onderdeel], onderdeel) for onderdeel in ONDERDELEN}
    rijen = []
    for sleutel, basis in sorted(delen["kengetallen"].items()):
        waarden = dict(basis["waarden"])
        for onderdeel, gelezen in delen.items():
            if onderdeel == "kengetallen":
                continue
            ander = gelezen.get(sleutel)
            if ander is None:
                waarden.update(dict.fromkeys(KOLOMMEN[onderdeel]))
                continue
            if (ander["sector"], ander["variant"]) != (basis["sector"], basis["variant"]):
                raise FinancienAfwijkend(f"{sleutel[0]} {sleutel[1]}: sector of variant verschilt in {onderdeel}")
            waarden.update(ander["waarden"])
        rijen.append(
            Bestuursjaar(
                sleutel=basis["sleutel"],
                naam=basis["naam"],
                sector=basis["sector"],
                groepering=basis["groepering"],
                verslagjaar=basis["verslagjaar"],
                variant=basis["variant"],
                waarden=waarden,
            )
        )
    return Financien(editie, tuple(rijen))


def laad(haler: Haler | None = None) -> Financien:
    """De nieuwste editie van mbo, hbo en wo: de pagina, dan de vier bestanden. `haler` vervangt de HTTP-laag
    (bijvoorbeeld een cache met If-Modified-Since); een HTTP-fout wordt `FinancienOnbereikbaar`."""
    haler = haler or haal
    pagina, _ = _veilig(haler, PAGINA)
    editie = lees_editie(pagina.decode("utf-8", errors="replace"))
    bestanden = {o: xlsx(*_veilig(haler, url), url) for o, url in editie.urls.items()}
    return lees(editie, bestanden)


# ── rekenen ───────────────────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Financien:
    editie: Editie
    rijen: tuple[Bestuursjaar, ...]

    def van(self, bestuur) -> list[Bestuursjaar]:
        """De verslagjaren van een bestuur (alle eenheden) of van één eenheid (`40833-25PZ`), op eenheid en jaar."""
        sleutel = bestuur if isinstance(bestuur, Bestuurssleutel) else Bestuurssleutel.parse(bestuur)
        if sleutel is None:
            return []
        if sleutel.brin is None:
            rijen = [r for r in self.rijen if r.sleutel.nummer == sleutel.nummer]
        else:
            rijen = [r for r in self.rijen if r.sleutel == sleutel]
        return sorted(rijen, key=lambda r: (str(r.sleutel), r.verslagjaar))

    def sectorcijfer(self, sector: str, verslagjaar: int, kengetal: str) -> Sectorcijfer:
        """Het gewogen sectorcijfer van de Inspectie (`SECTORMETHODE`)."""
        k = _KENGETAL[kengetal]
        teller = noemer = 0.0
        eenheden = zonder = 0
        for r in self.rijen:
            if r.sector != sector or r.verslagjaar != verslagjaar:
                continue
            posten = {p: r.waarden.get(p) for p in (*k.teller, *k.noemer)}
            if any(w is None for p, w in posten.items() if p not in _LEEG_IS_AFWEZIG):
                zonder += 1
                continue
            teller += sum(posten[p] or 0.0 for p in k.teller)
            noemer += sum(posten[p] or 0.0 for p in k.noemer)
            eenheden += 1
        waarde = teller / noemer if eenheden and noemer else None
        return Sectorcijfer(sector, verslagjaar, kengetal, waarde, eenheden, zonder)


def liquiditeitsgrens(baten: float | None) -> tuple[float, str] | None:
    """De signaleringswaarde voor liquiditeit bij deze totale baten, met de trede; None zonder baten."""
    if baten is None:
        return None
    if baten < 3_000_000:
        return LIQUIDITEIT_TREDEN[0]
    if baten <= 12_000_000:
        return LIQUIDITEIT_TREDEN[1]
    return LIQUIDITEIT_TREDEN[2] if baten <= 25_000_000 else LIQUIDITEIT_TREDEN[3]


def _onder(waarde: float | None, grens: float | None) -> bool | None:
    return None if waarde is None or grens is None else waarde < grens


def overzicht(financien: Financien, bestuur) -> list[dict]:
    """Per eenheid en verslagjaar de kengetallen, het sectorcijfer en de toets aan de signaleringswaarden.

    Platte rijen (voor een DataFrame), onafgerond; de kengetallen als fractie zoals DUO ze geeft (rentabiliteit
    0,02 = 2 %). Leeg als het bestuur niet bij mbo, hbo of wo staat.
    """
    uit = []
    for r in financien.van(bestuur):
        regel: dict = {
            "eenheid": str(r.sleutel),
            "naam": r.naam,
            "sector": r.sector,
            "groepering": r.groepering,
            "verslagjaar": r.verslagjaar,
            "variant": r.variant,
        }
        for k in KENGETALLEN:
            s = financien.sectorcijfer(r.sector, r.verslagjaar, k.sleutel)
            regel[k.sleutel] = r.waarden.get(k.sleutel)
            regel[f"{k.sleutel}_sector"] = s.waarde
            regel[f"{k.sleutel}_sector_eenheden"] = s.eenheden
        regel["rijksbijdragen"] = r.waarden.get("rijksbijdragen")
        regel["werkplaatsfunctie"] = r.waarden.get("werkplaatsfunctie")
        grens = liquiditeitsgrens(r.waarden.get("baten"))
        regel["solvabiliteit_2_signaleringswaarde"] = SOLVABILITEIT_2_GRENS
        regel["solvabiliteit_2_onder_signaleringswaarde"] = _onder(r.waarden.get("solvabiliteit_2"), SOLVABILITEIT_2_GRENS)
        regel["liquiditeit_signaleringswaarde"] = grens[0] if grens else None
        regel["liquiditeit_trede"] = grens[1] if grens else None
        regel["liquiditeit_onder_signaleringswaarde"] = _onder(r.waarden.get("liquiditeit"), grens[0] if grens else None)
        uit.append(regel)
    return uit

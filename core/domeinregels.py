"""De domeinregels voor DUO-data, uit data/domeinregels.toml (#363).

Regels die de tools afdwingen: de -1-sentinel, correcties op kolombeschrijvingen, bestanden
waarvan de plaatskolommen de vestiging zijn en de OPLEIDINGSVORM-codes. Elke regel heeft een
id, een bron en de datum waarop hij tegen die bron is nagegaan. Een databeheerder wijzigt het
bestand, niet de code; tests/test_domeinregels.py loopt over elke regel (docs/domeinregels.md).

Hier en niet in tools/: core.sentinels heeft de sentinelregel nodig en core hangt niet van tools
af. De tools lezen via tools.duo_meta.regels(), met dezelfde cache.

Faalt gesloten: een ongeldig bestand geeft bij het laden een DomeinregelFout, nooit lege regels
of standaardwaarden. Omdat core.sentinels bij import laadt, start de app dan niet.
"""

import tomllib
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import MISSING, dataclass, field, fields
from datetime import date
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, TypeVar

PAD = Path(__file__).resolve().parent.parent / "data" / "domeinregels.toml"

# Alleen de bron mag over meer regels lopen. Elke andere tekst geven de tools door, ook in gegenereerde
# Python (snippet) en in CSV-notities, waar een regeleinde een opdracht of formulerij zou beginnen.
Meerregelig = Annotated[str, "meerregelig"]


class DomeinregelFout(ValueError):
    """Het regelbestand is ongeldig; de melding noemt de regel en wat eraan mankeert."""


@dataclass(frozen=True)
class Regel:
    id: str
    bron: Meerregelig
    gecontroleerd: date


@dataclass(frozen=True)
class Sentinelregel(Regel):
    """Celwaarden die een onderdrukte cel zijn, geen telwaarde; niet in kolommen met een teken."""

    waarden: tuple[int, ...]
    betekenis: str
    uitgezonderd_als_kolom_bevat: tuple[str, ...]


@dataclass(frozen=True)
class Opleidingsvormregel(Regel):
    """De OPLEIDINGSVORM-codes, alleen voor de bestanden waarvan de beschrijving ze noemt."""

    datasets: tuple[str, ...]
    codes: Mapping[str, str]


@dataclass(frozen=True)
class Kolomcorrectie(Regel):
    """Een kolombeschrijving die in de bron fout of leeg is; gaat voor op riodata."""

    datasets: tuple[str, ...]
    kolom: str
    definitie: str


@dataclass(frozen=True)
class HerkomstIsVestiging(Regel):
    """Bestanden waarvan de plaatskolommen de vestiging zijn: geen bron voor woonplaats of herkomst."""

    datasets: tuple[str, ...]
    melding: str
    voorbeeldvragen: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class Domeinregels:
    sentinel: Sentinelregel
    opleidingsvorm: Opleidingsvormregel
    kolomcorrecties: tuple[Kolomcorrectie, ...]
    herkomst_is_vestiging: tuple[HerkomstIsVestiging, ...]

    def alle(self) -> tuple[Regel, ...]:
        return (self.sentinel, self.opleidingsvorm, *self.kolomcorrecties, *self.herkomst_is_vestiging)


# Per regelsoort de klasse, en of het bestand er precies één ([soort]) of een lijst ([[soort]]) van heeft.
# De velden van de klasse zijn het schema: een veld met een standaardwaarde is optioneel.
_SOORTEN: dict[str, tuple[type[Regel], bool]] = {
    "sentinel": (Sentinelregel, False),
    "opleidingsvorm": (Opleidingsvormregel, False),
    "kolomcorrectie": (Kolomcorrectie, True),
    "herkomst_is_vestiging": (HerkomstIsVestiging, True),
}
_SOORTNAAM = {klasse: soort for soort, (klasse, _) in _SOORTEN.items()}


class _Ongeldig(Exception):
    """Wat er mis is met één waarde; de aanroeper zet de regel en de sleutel ervoor."""


def _typenaam(waarde: object) -> str:
    namen = {bool: "waar/onwaar", str: "tekst", int: "getal", float: "kommagetal", list: "lijst", dict: "tabel"}
    return namen.get(type(waarde), type(waarde).__name__)


def _tekst(waarde: object) -> str:
    if not isinstance(waarde, str):
        raise _Ongeldig(f"moet tekst zijn, niet {_typenaam(waarde)}")
    if not waarde.strip():
        raise _Ongeldig("is leeg")
    return waarde


# Regeleinden (ook U+2028/U+2029), tabs, stuur- en opmaaktekens zoals bidi-overrides: geen van alle
# zichtbaar in een review van het bestand.
_GEEN_REGELTEKST = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


def _regeltekst(waarde: object) -> str:
    tekst = _tekst(waarde)
    if teken := next((t for t in tekst if unicodedata.category(t) in _GEEN_REGELTEKST), None):
        raise _Ongeldig(f"moet op één regel staan, zonder regeleinde of onzichtbaar teken (U+{ord(teken):04X})")
    return tekst


def _geheel_getal(waarde: object) -> int:
    if type(waarde) is not int:  # ook geen bool
        raise _Ongeldig(f"moet een geheel getal zijn, niet {_typenaam(waarde)}")
    return waarde


def _datum(waarde: object) -> date:
    if type(waarde) is not date:  # ook geen datum met tijd
        raise _Ongeldig(f"moet een datum zijn zonder aanhalingstekens (2026-10-08), niet {_typenaam(waarde)}")
    return waarde


def _lijst(element: Callable[[object], object]) -> Callable[[object], tuple]:
    def controleer(waarde: object) -> tuple:
        if not isinstance(waarde, list):
            raise _Ongeldig(f"moet een lijst zijn, niet {_typenaam(waarde)}")
        if not waarde:
            raise _Ongeldig("is een lege lijst")
        return tuple(_element(element, nr, w) for nr, w in enumerate(waarde, 1))

    return controleer


def _element(controleer: Callable[[object], object], nr: int, waarde: object) -> object:
    try:
        return controleer(waarde)
    except _Ongeldig as fout:
        raise _Ongeldig(f"element {nr} {fout}") from None


def _teksttabel(waarde: object) -> Mapping[str, str]:
    if not isinstance(waarde, dict):
        raise _Ongeldig(f"moet een tabel zijn, niet {_typenaam(waarde)}")
    if not waarde:
        raise _Ongeldig("is een lege tabel")
    return MappingProxyType({_regeltekst(k): _regeltekst(v) for k, v in waarde.items()})


# Per veldtype in de regelklassen: hoe een waarde uit het bestand wordt gecontroleerd.
_CONTROLE: dict[object, Callable[[object], object]] = {
    str: _regeltekst,
    Meerregelig: _tekst,
    date: _datum,
    tuple[str, ...]: _lijst(_regeltekst),
    tuple[int, ...]: _lijst(_geheel_getal),
    Mapping[str, str]: _teksttabel,
}

R = TypeVar("R", bound=Regel)


def _naam(soort: str, nr: int, regel_id: object) -> str:
    if isinstance(regel_id, str) and regel_id.strip():
        return f"regel '{regel_id}' ({soort})"
    return f"{soort} nr. {nr} (zonder id)"


def _opsomming(namen: Iterable[str]) -> str:
    return ", ".join(f"'{naam}'" for naam in namen)


def _regel(soort: str, nr: int, ruw: object) -> Regel:
    klasse = _SOORTEN[soort][0]
    if not isinstance(ruw, dict):
        raise DomeinregelFout(f"{soort} nr. {nr}: moet een tabel zijn, niet {_typenaam(ruw)}")
    naam = _naam(soort, nr, ruw.get("id"))
    velden = {veld.name: veld for veld in fields(klasse)}
    if onbekend := sorted(ruw.keys() - velden.keys()):
        raise DomeinregelFout(
            f"{naam}: onbekende sleutel {_opsomming(onbekend)} (typefout?); toegestaan: {_opsomming(velden)}"
        )
    waarden: dict[str, Any] = {}
    for sleutel, veld in velden.items():
        if sleutel in ruw:
            try:
                waarden[sleutel] = _CONTROLE[veld.type](ruw[sleutel])
            except _Ongeldig as fout:
                raise DomeinregelFout(f"{naam}: '{sleutel}' {fout}") from None
        elif veld.default is MISSING and veld.default_factory is MISSING:
            raise DomeinregelFout(f"{naam}: '{sleutel}' ontbreekt")
    return klasse(**waarden)


def _regels(ruw: dict, soort: str) -> tuple[Regel, ...]:
    waarde, lijst = ruw.get(soort), _SOORTEN[soort][1]
    if lijst:
        if waarde is None:
            return ()
        if not isinstance(waarde, list):
            raise DomeinregelFout(f"'{soort}' moet een lijst regels zijn ([[{soort}]]), niet {_typenaam(waarde)}")
        return tuple(_regel(soort, nr, regel) for nr, regel in enumerate(waarde, 1))
    if waarde is None:
        raise DomeinregelFout(f"regelsoort '{soort}' ontbreekt; de tools hebben hem nodig ([{soort}])")
    if not isinstance(waarde, dict):
        raise DomeinregelFout(f"'{soort}' moet één regel zijn ([{soort}]), niet {_typenaam(waarde)}")
    return (_regel(soort, 1, waarde),)


def _van(regels: tuple[Regel, ...], klasse: type[R]) -> tuple[R, ...]:
    return tuple(regel for regel in regels if isinstance(regel, klasse))


def _uniek(regels: Iterable[Regel], sleutels: Callable[[Any], Iterable], melding: str) -> None:
    """Geen sleutel in twee regels; `melding` krijgt {sleutel}, en {ander} en {soort} van de eerste regel."""
    eerste: dict[object, Regel] = {}
    for regel in regels:
        for sleutel in sleutels(regel):
            if (ander := eerste.setdefault(sleutel, regel)) is not regel:
                naam = _naam(_SOORTNAAM[type(regel)], 0, regel.id)
                details = melding.format(sleutel=sleutel, ander=ander.id, soort=_SOORTNAAM[type(ander)])
                raise DomeinregelFout(f"{naam}: {details}")


def _valideer(ruw: dict) -> Domeinregels:
    if onbekend := sorted(ruw.keys() - _SOORTEN.keys()):
        raise DomeinregelFout(f"onbekende regelsoort {_opsomming(onbekend)}; bekend: {_opsomming(_SOORTEN)}")
    per_soort = {soort: _regels(ruw, soort) for soort in _SOORTEN}
    regels = Domeinregels(
        sentinel=_van(per_soort["sentinel"], Sentinelregel)[0],
        opleidingsvorm=_van(per_soort["opleidingsvorm"], Opleidingsvormregel)[0],
        kolomcorrecties=_van(per_soort["kolomcorrectie"], Kolomcorrectie),
        herkomst_is_vestiging=_van(per_soort["herkomst_is_vestiging"], HerkomstIsVestiging),
    )
    _uniek(regels.alle(), lambda r: [r.id], "id '{sleutel}' staat ook bij een andere regel ({soort})")
    _uniek(
        regels.kolomcorrecties,
        lambda r: [(d, r.kolom) for d in r.datasets],
        "kolom {sleutel[1]} van {sleutel[0]} heeft al een correctie in regel '{ander}'",
    )
    _uniek(regels.herkomst_is_vestiging, lambda r: r.datasets, "dataset {sleutel} staat al in regel '{ander}'")
    return regels


@cache
def laad(pad: Path | None = None) -> Domeinregels:
    """De gevalideerde regels uit `pad`, standaard data/domeinregels.toml; elk gebrek is een DomeinregelFout."""
    pad = pad or PAD
    try:
        ruw = tomllib.loads(pad.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as fout:
        raise DomeinregelFout(f"{pad}: niet te lezen ({type(fout).__name__})") from fout
    except tomllib.TOMLDecodeError as fout:
        raise DomeinregelFout(f"{pad.name}: geen geldige TOML: {fout}") from fout
    try:
        return _valideer(ruw)
    except DomeinregelFout as fout:
        raise DomeinregelFout(f"{pad.name}: {fout}") from None

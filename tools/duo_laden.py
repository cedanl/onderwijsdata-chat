"""Een DUO-bestand laden met een encodingterugval en een controle op kolomdrift (#868).

`onderwijsbronnen.duo.load` leest een CSV met de standaardinstellingen van pandas (UTF-8), en leest de codekolommen als tekst
volgens een offline schema-snapshot van riodata. Twee dingen kunnen dan stil misgaan:

- DUO publiceert een bestand in cp1252: het laden faalt met een `UnicodeDecodeError`. Hier volgt dan een tweede
  poging met `encoding="cp1252"`, gelogd als `DUO_ENCODING`. Dat kost een tweede download, alleen voor zo'n bestand;
  een onthouden encoding zou een later UTF-8-bestand ongemerkt verminken, want cp1252 leest bijna alle bytes.
- DUO hernoemt, schrapt of voegt een kolom toe: het bestand laadt, maar een hernoemde codekolom valt buiten de
  tekstkolommen van de snapshot en wordt numeriek (voorloopnullen weg). Na het laden vergelijkt `controleer` de
  kolommen met de snapshot; een verschil gaat als `waarschuwing` in het toolresultaat en als `DUO_SCHEMA_DRIFT` in het
  log. Een bestand dat niet in de snapshot staat (een nieuwe resource-ID) heeft niets om mee te vergelijken: dat staat
  alleen in het log.

`kolommen_uit_kop` leest alleen de kopregel van een CSV, met dezelfde terugval: de bron-ping controleert zo alle
DUO-bestanden in het profiel zonder ze te downloaden (#869).
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import httpx
import pandas as pd
from onderwijsbronnen import duo as _duo

from . import bestandsversie
from .bronretry import haal_op_met_retry

logger = logging.getLogger(__name__)

TERUGVAL = "cp1252"
_KOP_MAX_BYTES = 64 * 1024
_KOP_TIMEOUT_S = 30
# Het rijnummer dat de CKAN-datastore toevoegt aan een dump (/datastore/dump/<id>); de snapshot telt het niet als kolom.
_DATASTORE_RIJNUMMER = "_id"


@dataclass(frozen=True)
class Kolomdrift:
    ontbrekend: tuple[str, ...]  # in de snapshot, niet in het bestand
    nieuw: tuple[str, ...]  # in het bestand, niet in de snapshot

    def verschil(self) -> str:
        """'ontbreekt: A; nieuw: B', voor het log van de bron-ping en de waarschuwing."""
        delen = (
            f"ontbreekt: {', '.join(self.ontbrekend)}" if self.ontbrekend else "",
            f"nieuw: {', '.join(self.nieuw)}" if self.nieuw else "",
        )
        return "; ".join(d for d in delen if d)

    def tekst(self) -> str:
        return (
            f"De kolommen van dit DUO-bestand wijken af van het schema dat de chat kent ({self.verschil()}). "
            "Een hernoemde codekolom kan als getal zijn gelezen, zonder voorloopnullen: controleer de kolommen "
            "voordat je op codes filtert of totalen noemt, en meld de afwijking bij het antwoord."
        )


# De drift van een geladen bestand, per md5 van de bytes: dezelfde bytes hebben dezelfde kolommen. Zo krijgt ook een
# gesprek dat het bestand uit de gedeelde store haalt de waarschuwing, zonder opnieuw te downloaden.
_drift_per_bestand: dict[str, Kolomdrift] = {}


def laad(dataset_id: str, resource: int | str) -> pd.DataFrame:
    """`onderwijsbronnen.duo.load` met herhaling bij een tijdelijke fout (#867) en een tweede poging in cp1252."""
    try:
        return haal_op_met_retry("DUO", lambda: _duo.load(dataset_id, resource))
    except UnicodeDecodeError:
        logger.warning("DUO_ENCODING dataset=%s resource=%s encoding=%s", dataset_id, resource, TERUGVAL)
        return haal_op_met_retry("DUO", lambda: _duo.load(dataset_id, resource, encoding=TERUGVAL))


def _snapshotkolommen(dataset_id: str, resource_id: str) -> list[str] | None:
    """De kolommen van dit bestand volgens de snapshot van riodata; None als de snapshot het bestand niet kent."""
    for schema in _duo.resource_schemas(dataset_id):
        if schema["resource_id"] == resource_id and schema["inspectie"]["status"] == "ok":
            return [k["naam"] for k in schema["kolommen"]]
    return None


def kolomdrift(dataset_id: str, resource_id: str | None, kolommen: list[str]) -> Kolomdrift | None:
    """Het verschil tussen `kolommen` en de snapshot; None als ze gelijk zijn of de snapshot het bestand niet kent."""
    verwacht = _snapshotkolommen(dataset_id, resource_id) if resource_id else None
    if verwacht is None:
        return None
    ontbrekend = tuple(k for k in verwacht if k not in kolommen)
    nieuw = tuple(k for k in kolommen if k not in verwacht and k != _DATASTORE_RIJNUMMER)
    return Kolomdrift(ontbrekend, nieuw) if ontbrekend or nieuw else None


def controleer(dataset_id: str, geladen: pd.DataFrame) -> Kolomdrift | None:
    """De kolomdrift van een net geladen bestand (uit `laad`), in het log en onthouden bij de md5 van het bestand."""
    bron = geladen.attrs.get("bron") or {}
    resource_id = bron.get("resource_id")
    if resource_id and _snapshotkolommen(dataset_id, resource_id) is None:
        logger.info("DUO_SCHEMA_DRIFT dataset=%s resource_id=%s niet_in_snapshot=1", dataset_id, resource_id)
        return None
    drift = kolomdrift(dataset_id, resource_id, [str(k) for k in geladen.columns])
    if drift is None:
        return None
    logger.warning(
        "DUO_SCHEMA_DRIFT dataset=%s resource_id=%s ontbrekend=%s nieuw=%s",
        dataset_id,
        resource_id,
        ",".join(drift.ontbrekend),
        ",".join(drift.nieuw),
    )
    if md5 := bestandsversie.bronhash(bron):
        _drift_per_bestand[md5] = drift
    return drift


def eerdere_drift(bronhash: str | None) -> Kolomdrift | None:
    """De drift die `controleer` vond voor het bestand met deze md5; None als er geen was of het onbekend is."""
    return _drift_per_bestand.get(bronhash) if bronhash else None


def lees_kop(inhoud: bytes, bron: str = "") -> list[str]:
    """De kolomnamen uit de eerste regel van een CSV; bij een UnicodeDecodeError opnieuw in cp1252."""
    kop = inhoud.split(b"\n", 1)[0]
    try:
        return [str(k) for k in pd.read_csv(io.BytesIO(kop), nrows=0).columns]
    except UnicodeDecodeError:
        logger.warning("DUO_ENCODING kopregel=%s encoding=%s", bron, TERUGVAL)
        return [str(k) for k in pd.read_csv(io.BytesIO(kop), nrows=0, encoding=TERUGVAL).columns]


def kolommen_uit_kop(url: str, bron: str = "") -> list[str]:
    """Alleen de kopregel van een DUO-CSV: lees tot de eerste regelovergang (hooguit 64 KiB), niet het hele bestand."""
    inhoud = b""
    with httpx.stream("GET", url, timeout=_KOP_TIMEOUT_S, follow_redirects=True) as antwoord:
        antwoord.raise_for_status()
        for stuk in antwoord.iter_bytes():
            inhoud += stuk
            if b"\n" in inhoud or len(inhoud) >= _KOP_MAX_BYTES:
                break
    return lees_kop(inhoud, bron)

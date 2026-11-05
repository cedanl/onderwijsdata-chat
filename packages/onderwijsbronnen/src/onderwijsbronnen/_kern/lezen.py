"""Gedeelde leeshulp voor CSV-downloads: aparte fouten per stap, herleidbare bron.

Stappen en hun fout: download (httpx), decoderen (``DecodeerFout``), parseren
(``ParserFout``) en schema (``SchemaFout``). Een parserfout wordt dus niet meer als
decodeerprobleem gemeld, en een verkeerde separator levert geen eentabel-kolomsucces op.
"""
from __future__ import annotations

import hashlib
import io

ENCODINGS = ("utf-8-sig", "latin-1", "cp1252")
MAX_BYTES = 500 * 1024 * 1024  # bovengrens voor download en uitgepakte CSV


class LeesFout(Exception):
    """Basis voor leesfouten van de package-loaders."""


class DecodeerFout(LeesFout, RuntimeError):
    """Bytes zijn niet als tekst te lezen (RuntimeError voor achterwaartse compatibiliteit)."""


class ParserFout(LeesFout, RuntimeError):
    """Tekst is gedecodeerd maar niet als CSV te parseren."""


class SchemaFout(LeesFout, ValueError):
    """Het bestand heeft niet de verwachte vorm (separator, kolommen)."""


class ChecksumFout(LeesFout, RuntimeError):
    """Het gedownloade bestand wijkt af van de gecontroleerde versie (checksum)."""


class LimietFout(LeesFout, RuntimeError):
    """Download of uitgepakt bestand is groter dan de toegestane limiet."""


def controleer_omvang(n_bytes: int, wat: str, limiet: int | None = None) -> None:
    limiet = MAX_BYTES if limiet is None else limiet
    if n_bytes > limiet:
        raise LimietFout(f"{wat} is {n_bytes} bytes; limiet is {limiet}")


def herkomst(content: bytes, url: str | None) -> dict:
    return {"bron_url": url, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def lees_csv(content: bytes, *, defaults: dict | None = None, verwacht: tuple[str, ...] = (), **kwargs):
    """Lees CSV-bytes als DataFrame.

    ``defaults`` zijn de standaard ``read_csv``-opties van de aanroeper (bijv. ``sep``); ``kwargs``
    van de gebruiker overschrijven ze, zoals voor deze PR. Is ``encoding`` opgegeven, dan wordt alleen
    die gebruikt; anders probeert de loader bij een ``UnicodeDecodeError`` de volgende encoding.
    Parserfouten stoppen meteen als ``ParserFout``. Een tabel met één kolom terwijl de kopregel een
    andere separator bevat, of waarin ``verwacht`` ontbreekt, geeft ``SchemaFout``.

    Returns (DataFrame, gebruikte_encoding).
    """
    import pandas as pd

    opties = {"sep": ",", **(defaults or {}), **kwargs}
    sep = opties["sep"]
    encodings = (opties.pop("encoding"),) if "encoding" in opties else ENCODINGS
    controleer_omvang(len(content), "CSV")
    laatste: UnicodeDecodeError | None = None
    for enc in encodings:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=enc, **opties)
        except UnicodeDecodeError as e:
            laatste = e
            continue
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
            raise ParserFout(f"CSV niet te parseren met separator {sep!r}: {e}") from e
        _controleer_schema(df, content, enc, sep, verwacht)
        return df, enc
    raise DecodeerFout(f"Niet te decoderen met {tuple(encodings)}: {laatste}")


def _controleer_schema(df, content: bytes, enc: str, sep: str, verwacht: tuple[str, ...]) -> None:
    if len(df.columns) == 1:
        kop = content.decode(enc, errors="replace").splitlines()[0] if content else ""
        andere = [s for s in (";", ",", "\t", "|") if s != sep and s in kop]
        if andere:
            raise SchemaFout(
                f"Slechts één kolom, maar de kopregel bevat {andere}: verkeerde separator "
                f"{sep!r}? Kolom: {list(df.columns)}"
            )
    ontbreekt = [c for c in verwacht if c not in df.columns]
    if ontbreekt:
        raise SchemaFout(f"Verwachte kolommen ontbreken: {ontbreekt}. Aanwezig: {list(df.columns)}")

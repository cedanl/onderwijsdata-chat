"""Het rapport als bewerkbaar Word-document (#1038): docxtpl vult templates/rapport.docx (Npuls-huisstijl).

Alle tekst komt uit het bewaarde rapport (uit_html.py) en is onvertrouwd (#634). Hij komt letterlijk in het document:
- autoescape staat aan, en `_letterlijk` (de finalize van Jinja) maakt van elke tekst XML-tekst: tekens die XML niet
  toestaat gaan eruit (docxtpl maakt van \\a en \\f anders een nieuwe alinea of pagina), `&`, `<` en `>` worden
  entiteiten, en `{` en `}` tekenverwijzingen, zodat docxtpl na het renderen geen `{_{` in `{{` verandert;
- tekst met opmaak (vet, een link, een regeleinde) bouwt `Runs` met dezelfde escaping, niet RichText van docxtpl;
- een link alleen voor een http(s)-adres (uit_html.veilige_url, dezelfde regel als bronLink.js).
De Jinja-code staat alleen in het sjabloon; niets uit het rapport wordt als sjabloon gelezen.
"""

import re
from collections.abc import Mapping
from html import escape
from io import BytesIO
from pathlib import Path

from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from jinja2 import Environment, StrictUndefined

from .afbeeldingen import Grafiek
from .uit_html import Blok, Definitie, Rapport, Visualisatie, conclusie_blokken

SJABLOON = Path(__file__).resolve().parents[2] / "templates" / "rapport.docx"

# De breedte van een grafiek op A4 (de tekstkolom is 166 mm) en de hoogste grafiek die op een pagina past.
BEELD_BREEDTE_MM = 160
BEELD_HOOGTE_MAX_MM = 200

_ONGELDIG_IN_XML = re.compile(r"[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")
_VET = re.compile(r"\*\*(.+?)\*\*")


def schoon(tekst: object) -> str:
    """Tekst zonder tekens die XML niet toestaat; tab en regeleinde worden een spatie."""
    return re.sub(r"[\t\n\r]", " ", _ONGELDIG_IN_XML.sub("", "" if tekst is None else str(tekst)))


def xml_tekst(tekst: object) -> str:
    return escape(schoon(tekst), quote=False).replace("{", "&#123;").replace("}", "&#125;")


class _Xml(str):
    """Kant-en-klare XML voor het sjabloon: autoescape laat een waarde met __html__ ongemoeid."""

    def __html__(self) -> str:
        return str(self)


def _letterlijk(waarde: object) -> object:
    if hasattr(waarde, "__html__"):
        return waarde
    return _Xml(xml_tekst(waarde))


class Runs:
    """Runs voor `{{r … }}` in het sjabloon: tekst, vet, een link (stijl Hyperlink) en regeleinden."""

    def __init__(self) -> None:
        self._xml: list[str] = []

    def tekst(self, tekst: str, *, vet: bool = False) -> "Runs":
        if tekst:
            opmaak = "<w:rPr><w:b/></w:rPr>" if vet else ""
            self._xml.append(f'<w:r>{opmaak}<w:t xml:space="preserve">{xml_tekst(tekst)}</w:t></w:r>')
        return self

    def link(self, tekst: str, relatie_id: str) -> "Runs":
        run = (
            f'<w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr><w:t xml:space="preserve">{xml_tekst(tekst)}</w:t></w:r>'
        )
        self._xml.append(f'<w:hyperlink r:id="{escape(relatie_id)}">{run}</w:hyperlink>')
        return self

    def regeleinde(self) -> "Runs":
        self._xml.append("<w:r><w:br/></w:r>")
        return self

    def __html__(self) -> str:
        return "".join(self._xml)

    def __bool__(self) -> bool:
        return bool(self._xml)


def met_vet(regel: str, runs: Runs | None = None) -> Runs:
    """Eén regel met **vet** (zo stond het in de conclusie, reportHtml.js) als runs."""
    runs = runs if runs is not None else Runs()
    for i, stuk in enumerate(_VET.split(regel)):
        runs.tekst(stuk, vet=i % 2 == 1)
    return runs


def _regels(regels: tuple[str, ...]) -> Runs:
    runs = Runs()
    for i, regel in enumerate(regels):
        if i:
            runs.regeleinde()
        met_vet(regel, runs)
    return runs


def _vette_cel(cel: str) -> Runs:
    """Een kopcel van een tabel: helemaal vet, dus zonder de **-tekens."""
    return Runs().tekst(_VET.sub(r"\1", cel), vet=True)


def _blok(blok: Blok) -> dict:
    return {
        "soort": blok.soort,
        "runs": _regels(blok.regels),
        "kop": [_vette_cel(cel) for cel in blok.kop],
        "rijen": [[met_vet(cel) for cel in rij] for rij in blok.rijen],
    }


def _definitie(d: Definitie) -> dict:
    enkel = d.delen[0] if len(d.delen) == 1 else ""
    na_begrip = f": {enkel}" if enkel and d.begrip else enkel
    return {"begrip": d.begrip, "na_begrip": na_begrip, "delen": list(d.delen) if len(d.delen) > 1 else []}


def _bron(tpl: DocxTemplate, v: Visualisatie) -> Runs | None:
    if not v.bron.regel and not v.bron.url:
        return None
    runs = Runs().tekst(v.bron.regel)
    if v.bron.url:
        if v.bron.regel:
            runs.tekst(" · ")
        runs.link(v.bron.link_tekst or "Bekijk de bron", tpl.build_url_id(v.bron.url))
    return runs


def _afbeelding(tpl: DocxTemplate, grafiek: Grafiek | None) -> InlineImage | None:
    if grafiek is None:
        return None
    breedte = BEELD_BREEDTE_MM
    hoogte = breedte * grafiek.hoogte_px / grafiek.breedte_px
    if hoogte > BEELD_HOOGTE_MAX_MM:
        breedte, hoogte = breedte * BEELD_HOOGTE_MAX_MM / hoogte, BEELD_HOOGTE_MAX_MM
    return InlineImage(tpl, BytesIO(grafiek.png), width=Mm(breedte), height=Mm(hoogte))


def _visualisatie(tpl: DocxTemplate, i: int, v: Visualisatie, grafiek: Grafiek | None) -> dict:
    return {
        "titel": v.titel or f"Visualisatie {i + 1}",
        "afbeelding": _afbeelding(tpl, grafiek),
        "noot": v.noot,
        "bron": _bron(tpl, v),
        "toelichting": v.toelichting,
    }


def context(tpl: DocxTemplate, rapport: Rapport, grafieken: Mapping[int, Grafiek]) -> dict:
    """Alle velden die het sjabloon gebruikt. Een lege sectie is leeg, en het sjabloon laat haar dan weg."""
    r = rapport
    meta = [*r.meta, f"Instelling: {r.instelling}" if r.instelling else ""]
    return {
        "titel": r.titel or "Rapport",
        "metaregel": " · ".join(m for m in meta if m),
        "afwijkingen": list(r.afwijkingen),
        "onderzoeksvraag": r.onderzoeksvraag,
        "beantwoordt": list(r.beantwoordt),
        "beantwoordt_niet": list(r.beantwoordt_niet),
        "definities": [_definitie(d) for d in r.definities],
        "visualisaties": [_visualisatie(tpl, i, v, grafieken.get(i)) for i, v in enumerate(r.visualisaties)],
        "conclusie": [_blok(b) for b in conclusie_blokken(r.conclusie)],
        "bronnen": list(r.bronnen),
        "herkomst": list(r.herkomst),
    }


def omgeving() -> Environment:
    return Environment(autoescape=True, finalize=_letterlijk, undefined=StrictUndefined)


def render_docx(rapport: Rapport, grafieken: Mapping[int, Grafiek], sjabloon: Path = SJABLOON) -> bytes:
    tpl = DocxTemplate(sjabloon)
    tpl.render(context(tpl, rapport, grafieken), omgeving(), autoescape=True)
    # tpl.docx, niet tpl.get_docx(): dat laadt na het renderen het lege sjabloon opnieuw.
    if (document := tpl.docx) is not None:
        document.core_properties.title = schoon(rapport.titel or "Rapport")
    uit = BytesIO()
    tpl.save(uit)
    return uit.getvalue()

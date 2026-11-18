"""De tekst van een bewaard rapport, gelezen uit zijn HTML (#1038): de Python-tweeling van rapportUitHtml.js (#746).

Een rapport wordt alleen als HTML bewaard (reportHtml.js); de spec is na het bewaren weg. Die HTML is onvertrouwd
(#634): lxml bouwt er een inerte boom van, er loopt geen script, en er komt alleen tekst uit, plus een link die een
http(s)-adres is (dezelfde regel als bronLink.js). Dezelfde selectors als de JS-tweeling, als XPath (lxml heeft zonder
cssselect geen CSS-selectors); een onderdeel dat een ouder rapport niet heeft, blijft leeg.

De conclusie gaat eerst terug naar de Markdown waaruit reportHtml.js haar maakte (zoals proseMarkdown in de JS) en
daarna naar blokken: kop, alinea, opsommingspunt of tabel. Een pipetabel (`| a | b |` met een `|---|---|`-regel
eronder, prompts/system.md) stond in de HTML als tekstregels; hier wordt het weer een tabel.
"""

import re
from dataclasses import dataclass
from typing import Literal, TypeGuard

from lxml import html as lxml_html

_HTTP_URL = re.compile(r"^https?://", re.IGNORECASE)
# Een stuurteken of een teken dat XML niet toestaat kan niet in de koppeling van het document (lxml weigert het).
_ONGELDIG_IN_URL = re.compile(r"[\x00-\x1f\x7f\ud800-\udfff\ufffe\uffff]")
_KOP = re.compile(r"^h[1-6]$")
_SCHEIDING = re.compile(r"^\|(\s*:?-+:?\s*\|)+$")


@dataclass(frozen=True)
class Bronregel:
    regel: str
    url: str | None
    link_tekst: str


@dataclass(frozen=True)
class Definitie:
    begrip: str
    delen: tuple[str, ...]


@dataclass(frozen=True)
class Visualisatie:
    titel: str
    noot: str
    bron: Bronregel
    toelichting: str


@dataclass(frozen=True)
class Blok:
    """Eén blok van de conclusie. Een alinea heeft één of meer regels; kop en punt één; een tabel kop en rijen."""

    soort: Literal["kop", "alinea", "punt", "tabel"]
    regels: tuple[str, ...] = ()
    kop: tuple[str, ...] = ()
    rijen: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Rapport:
    titel: str
    meta: tuple[str, ...]
    instelling: str
    afwijkingen: tuple[str, ...]
    onderzoeksvraag: str
    beantwoordt: tuple[str, ...]
    beantwoordt_niet: tuple[str, ...]
    definities: tuple[Definitie, ...]
    visualisaties: tuple[Visualisatie, ...]
    conclusie: str
    bronnen: tuple[str, ...]
    herkomst: tuple[str, ...]


def kan_docx(html: object) -> TypeGuard[str]:
    """Een rapport uit buildReportHtml heeft altijd het blok met de onderzoeksvraag (kanMarkdown in de JS)."""
    return isinstance(html, str) and 'class="vraag"' in html


def _tekst(el) -> str:
    return re.sub(r"\s+", " ", el.text_content() if el is not None else "").strip()


def _klasse(naam: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {naam} ')"


def _alle(root, xpath: str) -> list:
    return root.xpath(xpath)


def _eerste(root, xpath: str):
    gevonden = root.xpath(xpath)
    return gevonden[0] if gevonden else None


def _teksten(root, xpath: str) -> tuple[str, ...]:
    return tuple(t for t in (_tekst(el) for el in root.xpath(xpath)) if t)


def veilige_url(url: object) -> str | None:
    """Het adres als het een http(s)-adres is, anders None (veiligeBronUrl in bronLink.js).

    Strenger dan de JS-tweeling: een adres met een stuurteken wordt geen link, want het moet in de XML van het document.
    """
    if not isinstance(url, str) or not _HTTP_URL.match(url) or _ONGELDIG_IN_URL.search(url):
        return None
    return url


def _definitie(el) -> Definitie:
    lijst = _teksten(el, f".//*[{_klasse('def-lijst')}]//li")
    delen = lijst or tuple(t for t in (_tekst(_eerste(el, f".//*[{_klasse('def-desc')}]")),) if t)
    return Definitie(begrip=_tekst(_eerste(el, f".//*[{_klasse('def-term')}]")), delen=delen)


def _bronregel(el) -> Bronregel:
    """De bronregel onder een grafiek (#569): de regel zonder de link, en de link apart."""
    if el is None:
        return Bronregel(regel="", url=None, link_tekst="")
    link = _eerste(el, ".//a")
    link_tekst = _tekst(link)
    href = link.get("href") if link is not None else None
    if link is not None:
        link.drop_tree()
    return Bronregel(regel=re.sub(r"\s*·$", "", _tekst(el)), url=veilige_url(href), link_tekst=link_tekst)


def _visualisatie(el) -> Visualisatie:
    return Visualisatie(
        titel=_tekst(_eerste(el, f".//*[{_klasse('vis-title')}]")),
        noot=_tekst(_eerste(el, f".//*[{_klasse('vis-noot')}]")),
        bron=_bronregel(_eerste(el, f".//*[{_klasse('vis-bron')}]")),
        toelichting=_tekst(_eerste(el, f".//*[{_klasse('vis-note')}]")),
    )


def _spaties(tekst: str | None) -> str:
    return re.sub(r"\s+", " ", tekst or "")


def _prose_markdown(el) -> str:
    """De conclusie terug naar Markdown, zoals proseMarkdown in rapportUitHtml.js: koppen, vet, punten en regels."""
    uit = _spaties(el.text)
    for kind in el:
        if isinstance(kind.tag, str):
            binnen = _prose_markdown(kind)
            tag = kind.tag.lower()
            if tag == "br":
                uit += "\n"
            elif tag in ("strong", "b"):
                uit += f"**{binnen.strip()}**"
            elif _KOP.match(tag):
                uit += f"\n\n### {binnen.strip()}\n\n"
            elif tag == "li":
                uit += f"\n- {binnen.strip()}\n"
            elif tag in ("p", "div", "ul", "ol"):
                uit += f"\n\n{binnen}\n\n"
            else:
                uit += binnen
        uit += _spaties(kind.tail)
    return uit


def _netjes(markdown: str) -> str:
    """Regels zonder randspaties, hooguit één lege regel achter elkaar, en geen lege regel binnen een opsomming."""
    regels = [r.strip() for r in markdown.split("\n")]
    regels = [r for i, r in enumerate(regels) if r or (i > 0 and regels[i - 1])]

    def in_opsomming(i: int) -> bool:
        return 0 < i < len(regels) - 1 and regels[i - 1].startswith("- ") and regels[i + 1].startswith("- ")

    return "\n".join(r for i, r in enumerate(regels) if r or not in_opsomming(i)).strip()


def _cellen(regel: str) -> list[str]:
    binnen = regel.strip().removeprefix("|").removesuffix("|")
    return [c.strip() for c in binnen.split("|")]


def _is_pipe(regel: str) -> bool:
    return regel.startswith("|") and regel.endswith("|") and len(regel) > 1


def _tabel(regels: list[str]) -> Blok:
    kop = _cellen(regels[0])
    breedte = len(kop)
    rijen = tuple(tuple((_cellen(r) + [""] * breedte)[:breedte]) for r in regels[2:])
    return Blok(soort="tabel", kop=tuple(kop), rijen=rijen)


def conclusie_blokken(markdown: str) -> tuple[Blok, ...]:
    """De conclusie als blokken. Opeenvolgende pipe-regels met een scheidingsregel als tweede worden een tabel;
    zonder scheidingsregel blijven ze tekst. Regels zonder lege regel ertussen vormen één alinea."""
    regels = markdown.split("\n")
    blokken: list[Blok] = []
    alinea: list[str] = []

    def sluit_alinea() -> None:
        if alinea:
            blokken.append(Blok(soort="alinea", regels=tuple(alinea)))
            alinea.clear()

    i = 0
    while i < len(regels):
        regel = regels[i]
        if _is_pipe(regel) and i + 1 < len(regels) and _SCHEIDING.match(regels[i + 1]):
            eind = i + 2
            while eind < len(regels) and _is_pipe(regels[eind]):
                eind += 1
            sluit_alinea()
            blokken.append(_tabel(regels[i:eind]))
            i = eind
            continue
        if regel.startswith("### "):
            sluit_alinea()
            blokken.append(Blok(soort="kop", regels=(regel.removeprefix("### "),)))
        elif regel.startswith("- "):
            sluit_alinea()
            blokken.append(Blok(soort="punt", regels=(regel.removeprefix("- "),)))
        elif regel:
            alinea.append(regel)
        else:
            sluit_alinea()
        i += 1
    sluit_alinea()
    return tuple(blokken)


def _document(html: str):
    """Een lege of onleesbare HTML is een leeg document (lxml geeft dan een ParserError of ValueError)."""
    try:
        return lxml_html.document_fromstring(html)
    except (lxml_html.etree.ParserError, ValueError):
        return lxml_html.document_fromstring("<html><body></body></html>")


def rapport_uit_html(html: str) -> Rapport:
    doc = _document(str(html or ""))
    prose = _eerste(doc, f"//*[{_klasse('conf')}]//*[{_klasse('prose')}]")
    scope = "//*[{}]/following-sibling::*[1][self::ul]//li"
    return Rapport(
        titel=_tekst(_eerste(doc, f"//*[{_klasse('header')}]//h1")),
        meta=_teksten(doc, f"//*[{_klasse('meta-chip')}]"),
        instelling=_tekst(_eerste(doc, f"//*[{_klasse('instelling-badge')}]")),
        afwijkingen=_teksten(doc, f"//*[{_klasse('afwijking')}]//li"),
        onderzoeksvraag=_tekst(_eerste(doc, f"//*[{_klasse('vraag-text')}]")),
        beantwoordt=_teksten(doc, scope.format(_klasse("scope-yes"))),
        beantwoordt_niet=_teksten(doc, scope.format(_klasse("scope-no"))),
        definities=tuple(_definitie(el) for el in _alle(doc, f"//*[{_klasse('def')}]")),
        visualisaties=tuple(_visualisatie(el) for el in _alle(doc, f"//*[{_klasse('vis')}]")),
        conclusie=_netjes(_prose_markdown(prose)) if prose is not None else "",
        bronnen=_teksten(doc, f"//*[{_klasse('bronnen')}]//li"),
        herkomst=_teksten(doc, f"//*[{_klasse('manifest')}]/div"),
    )

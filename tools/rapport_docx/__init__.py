"""Het rapport als bewerkbaar Word-document (#1038): lezen uit de bewaarde HTML, grafieken controleren, renderen."""

from .afbeeldingen import AfbeeldingFout, Grafiek, lees_grafieken
from .render import render_docx
from .uit_html import Rapport, kan_docx, rapport_uit_html

__all__ = ["AfbeeldingFout", "Grafiek", "Rapport", "kan_docx", "lees_grafieken", "rapport_uit_html", "render_docx"]

import io
import re
import tempfile
import os
from datetime import date
import html as html_module

import markdown as md
import plotly.graph_objects as go
import plotly.io as pio
from fpdf import FPDF


def generate_report(turns: list[dict]) -> str:
    sections_html = ""
    first_plotly_js = True

    for i, turn in enumerate(turns, 1):
        question = html_module.escape(turn.get("question", ""))
        answer = turn.get("answer", "") or ""
        figures: list[go.Figure] = turn.get("figures", [])

        answer_html = md.markdown(answer, extensions=["nl2br"])

        charts_html = ""
        for fig in figures:
            charts_html += pio.to_html(fig, include_plotlyjs="cdn" if first_plotly_js else False, full_html=False)
            first_plotly_js = False

        sections_html += f"""
<div class="turn">
  <div class="user"><strong>Vraag {i}:</strong> {question}</div>
  <div class="assistant"><strong>Interpretatie:</strong> {answer_html}</div>
  {charts_html}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>Onderwijsdata rapport — {date.today()}</title>
<style>
  body {{ font-family: sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ font-size: 1.5rem; border-bottom: 2px solid #ddd; padding-bottom: .5rem; }}
  .turn {{ border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem 1.5rem; margin: 1.5rem 0; }}
  .user {{ background: #f0f4ff; border-left: 4px solid #4a6cf7; padding: .75rem 1rem; margin-bottom: 1rem; border-radius: 2px; }}
  .assistant {{ background: #f9f9f9; border-left: 4px solid #aaa; padding: .75rem 1rem; margin-top: 1rem; border-radius: 2px; }}
  .assistant p {{ margin: .4rem 0; }}
  .assistant ul, .assistant ol {{ margin: .4rem 0 .4rem 1.5rem; }}
</style>
</head>
<body>
<h1>Onderwijsdata rapport</h1>
<p>Gegenereerd op {date.today().strftime("%-d %B %Y")}</p>
{sections_html if sections_html else "<p>Geen gesprek in dit rapport.</p>"}
</body>
</html>"""


def _plotly_to_png(fig: go.Figure) -> bytes:
    return pio.to_image(fig, format="png", width=900, height=450, scale=2)


def _extract_bronnen(turns: list[dict]) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for turn in turns:
        answer = turn.get("answer") or ""
        in_bronnen = False
        for line in answer.splitlines():
            if re.match(r"\*?\*?Bronnen\*?\*?", line.strip(), re.IGNORECASE):
                in_bronnen = True
                continue
            if in_bronnen:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    in_bronnen = False
                    continue
                if stripped not in seen:
                    seen.add(stripped)
                    lines.append(stripped)
    return "\n".join(lines)


def generate_rapport_html(
    title: str,
    samenvatting: str,
    conclusie: str,
    turns: list[dict],
) -> str:
    bronnen_raw = _extract_bronnen(turns)
    bronnen_html = md.markdown(bronnen_raw, extensions=["nl2br"]) if bronnen_raw else ""

    charts_html = ""
    first_plotly_js = True
    for turn in turns:
        for fig in turn.get("figures", []):
            charts_html += pio.to_html(
                fig,
                include_plotlyjs="cdn" if first_plotly_js else False,
                full_html=False,
                config={"displayModeBar": False},
            )
            first_plotly_js = False

    title_esc = html_module.escape(title)
    samenvatting_esc = html_module.escape(samenvatting)
    conclusie_esc = html_module.escape(conclusie) if conclusie else ""

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    font-family: "Inter", "Segoe UI", Arial, sans-serif;
    font-size: 15px;
    line-height: 1.65;
    color: #1a1a2e;
    background: #f8f9fc;
    margin: 0;
    padding: 2rem 1rem 4rem;
  }}
  .page {{ max-width: 900px; margin: 0 auto; }}
  header {{
    border-bottom: 3px solid #2563eb;
    padding-bottom: 1.25rem;
    margin-bottom: 2rem;
  }}
  header h1 {{ font-size: 1.75rem; font-weight: 700; margin: 0 0 .3rem; }}
  header .meta {{ font-size: .82rem; color: #6b7280; margin: 0; }}
  .blok {{
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.25rem;
    margin-bottom: 2rem;
  }}
  .blok h2 {{
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    margin: 0 0 .5rem;
  }}
  .blok p {{ margin: 0; font-size: 1rem; }}
  .samenvatting {{ background: #eff6ff; border-left: 4px solid #2563eb; }}
  .samenvatting h2 {{ color: #2563eb; }}
  .samenvatting p {{ color: #1e3a5f; }}
  .conclusie {{ background: #f0fdf4; border-left: 4px solid #16a34a; }}
  .conclusie h2 {{ color: #16a34a; }}
  .conclusie p {{ color: #14532d; }}
  .charts {{ margin-bottom: 2rem; }}
  .bronnen {{
    margin-top: 2.5rem;
    border-top: 1px solid #e5e7eb;
    padding-top: 1.25rem;
  }}
  .bronnen h2 {{
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #6b7280;
    margin: 0 0 .75rem;
  }}
  .bronnen p, .bronnen li {{ font-size: .82rem; color: #6b7280; }}
  .bronnen ul {{ margin: 0; padding-left: 1.25rem; }}
  footer {{ margin-top: 2rem; text-align: center; font-size: .75rem; color: #9ca3af; }}
</style>
</head>
<body>
<div class="page">

<header>
  <h1>{title_esc}</h1>
  <p class="meta">Onderwijsdata rapport &middot; {date.today().strftime("%-d %B %Y")}</p>
</header>

<div class="blok samenvatting">
  <h2>Samenvatting</h2>
  <p>{samenvatting_esc}</p>
</div>

<div class="charts">
{charts_html if charts_html else "<p>Geen visualisaties geselecteerd.</p>"}
</div>

{f'<div class="blok conclusie"><h2>Conclusie</h2><p>{conclusie_esc}</p></div>' if conclusie_esc else ""}

{f'<div class="bronnen"><h2>Bronnen</h2>{bronnen_html}</div>' if bronnen_html else ""}

<footer>Gegenereerd vanuit onderwijsdata-chat</footer>
</div>
</body>
</html>"""


def _to_latin1(text: str) -> str:
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^[-*]\s+", "- ", text, flags=re.MULTILINE)
    return _to_latin1(text).strip()


def generate_pdf(turns: list[dict]) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Onderwijsdata rapport", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Gegenereerd op {date.today().strftime('%-d %B %Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    for i, turn in enumerate(turns, 1):
        question = _to_latin1(turn.get("question", ""))
        answer = _strip_markdown(turn.get("answer", "") or "")
        figures: list[go.Figure] = turn.get("figures", [])

        pdf.set_fill_color(240, 244, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 7, f"Vraag {i}: {question}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, answer, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        for fig in figures:
            png = _plotly_to_png(fig)
            pdf.image(io.BytesIO(png), w=pdf.epw)
            pdf.ln(3)

        pdf.ln(4)

    return bytes(pdf.output())

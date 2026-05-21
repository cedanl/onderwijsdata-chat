import io
import re
import tempfile
import os
from datetime import date
import html as html_module

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
    dpi = 100
    mpl_fig, ax = plt.subplots(figsize=(7, 3.8), dpi=dpi)

    for trace in fig.data:
        t = trace.type
        name = trace.name or ""
        color = None
        if hasattr(trace, "marker") and trace.marker and hasattr(trace.marker, "color"):
            c = trace.marker.color
            if isinstance(c, str):
                color = c

        x = list(trace.x) if getattr(trace, "x", None) is not None else []
        y = list(trace.y) if getattr(trace, "y", None) is not None else []

        if t == "bar":
            ax.bar(x, y, label=name, color=color)
        elif t in ("scatter", "scattergl"):
            mode = getattr(trace, "mode", None) or "lines"
            if "markers" in mode and "lines" in mode:
                ax.plot(x, y, "o-", label=name, color=color, markersize=4, linewidth=1.5)
            elif "markers" in mode:
                ax.scatter(x, y, label=name, color=color, s=25)
            else:
                ax.plot(x, y, label=name, color=color, linewidth=1.5)
        elif t == "pie":
            vals = list(trace.values) if getattr(trace, "values", None) is not None else []
            lbls = list(trace.labels) if getattr(trace, "labels", None) is not None else []
            ax.pie(vals, labels=lbls, autopct="%1.0f%%")
        elif t == "histogram":
            src = x or y
            ax.hist(src, label=name, color=color, alpha=0.8)

    layout = fig.layout
    if layout.title and layout.title.text:
        ax.set_title(layout.title.text, fontsize=11)
    if layout.xaxis and layout.xaxis.title and layout.xaxis.title.text:
        ax.set_xlabel(layout.xaxis.title.text, fontsize=9)
    if layout.yaxis and layout.yaxis.title and layout.yaxis.title.text:
        ax.set_ylabel(layout.yaxis.title.text, fontsize=9)
    if layout.barmode == "group":
        pass  # matplotlib renders grouped bars automatically when multiple bar calls made

    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend(fontsize=8)

    ax.tick_params(labelsize=8)
    mpl_fig.tight_layout()

    buf = io.BytesIO()
    mpl_fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(mpl_fig)
    buf.seek(0)
    return buf.read()


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

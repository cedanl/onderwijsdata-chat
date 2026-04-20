from datetime import date
import html as html_module

import markdown as md
import plotly.graph_objects as go
import plotly.io as pio


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
  {charts_html}
  <div class="assistant"><strong>Interpretatie:</strong> {answer_html}</div>
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

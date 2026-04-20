from datetime import date

import plotly.graph_objects as go
import plotly.io as pio


def generate_report(messages: list[dict], figures: list[go.Figure]) -> str:
    chart_html = ""
    for i, fig in enumerate(figures):
        include_js = "cdn" if i == 0 else False
        chart_html += pio.to_html(fig, include_plotlyjs=include_js, full_html=False)

    conversation_html = ""
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content") or ""
        if not isinstance(content, str):
            continue
        if role == "user":
            conversation_html += f'<div class="user"><strong>Vraag:</strong> {content}</div>'
        elif role == "assistant":
            conversation_html += f'<div class="assistant"><strong>Interpretatie:</strong> {content}</div>'

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>Onderwijsdata rapport — {date.today()}</title>
<style>
  body {{ font-family: sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ font-size: 1.5rem; border-bottom: 2px solid #ddd; padding-bottom: .5rem; }}
  .user {{ background: #f0f4ff; border-left: 4px solid #4a6cf7; padding: .75rem 1rem; margin: 1rem 0; }}
  .assistant {{ background: #f9f9f9; border-left: 4px solid #aaa; padding: .75rem 1rem; margin: 1rem 0; white-space: pre-wrap; }}
  .charts {{ margin: 2rem 0; }}
  .section {{ margin-top: 2.5rem; }}
</style>
</head>
<body>
<h1>Onderwijsdata rapport</h1>
<p>Gegenereerd op {date.today().strftime("%-d %B %Y")}</p>

<div class="section charts">
  <h2>Grafieken</h2>
  {chart_html if chart_html else "<p>Geen grafieken in dit gesprek.</p>"}
</div>

<div class="section">
  <h2>Gesprek &amp; interpretatie</h2>
  {conversation_html}
</div>
</body>
</html>"""

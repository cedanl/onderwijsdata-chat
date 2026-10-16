"""Algemene feedback (de Feedback-link, #600) als markdown-overzicht voor het team.

Draait tegen dezelfde database als de app (DATABASE_PATH of POSTGRES_URI), bijvoorbeeld
vanuit /app in de pod: `/app/.venv/bin/python -m scripts.algemene_feedback > algemeen.md`.
"""

from core.algemene_feedback import als_markdown
from persistence import db

if __name__ == "__main__":
    print(als_markdown(db.all_algemene_feedback()), end="")

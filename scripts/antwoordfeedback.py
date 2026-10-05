"""Feedback per antwoord als markdown-overzicht voor het team (#248).

Draait tegen dezelfde database als de app (DATABASE_PATH of POSTGRES_URI), bijvoorbeeld
vanuit /app in de pod: `/app/.venv/bin/python -m scripts.antwoordfeedback > feedback.md`.
"""

from core.answer_feedback import als_markdown
from persistence import db

if __name__ == "__main__":
    print(als_markdown(db.all_answer_feedback()), end="")

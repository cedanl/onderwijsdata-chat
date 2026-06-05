import asyncio
import csv
import io
import os
import tempfile
from datetime import date

from dotenv import load_dotenv

load_dotenv()

import litellm
import chainlit as cl

import auth
import data_layer
from agent import generate_title, run
from chainlit.data import get_data_layer
from config import MODEL, WILLMA_API_KEY, get_available_models
from report import generate_pdf, generate_report
from resume import build_messages_from_thread, build_turns_from_thread

auth.setup()
data_layer.setup()

WELKOM = """Welkom! Ik kan je helpen met vragen over open Nederlandse onderwijsdata.

Ik heb toegang tot:
- **CBS** — statistieken over het Nederlandse onderwijs (68 datasets)
- **RIO** — register van onderwijsinstellingen en opleidingen (14 resources)
- **DUO** — 57 open datasets: prognoses, diplomering, instroom, adressen (onderwijsdata.duo.nl)

Stel een vraag, bijvoorbeeld:
- *Hoeveel MBO studenten waren er in 2023?*
- *Welke HBO-instellingen zijn er in Amsterdam?*
- *Wat is het verschil in uitstroom tussen mannen en vrouwen in het WO?*
- *Hoe ontwikkelt het MBO-studentenaantal zich richting 2040 per leerweg?*
"""

_FRIENDLY_ERRORS: list[tuple[type, str]] = [
    (litellm.AuthenticationError, "API key ontbreekt of is ongeldig. Controleer je `.env` bestand."),
    (litellm.NotFoundError, "Model niet gevonden. Controleer de `MODEL` instelling in `.env`."),
    (litellm.RateLimitError, "Te veel verzoeken naar de API. Wacht even en probeer opnieuw."),
    (litellm.APIConnectionError, "Kan de API niet bereiken. Controleer je internetverbinding."),
    (litellm.BadRequestError, "Het verzoek werd afgewezen door de API. Mogelijk een ongeldig model of parameter."),
]


def _friendly_error(exc: Exception) -> str:
    for exc_type, msg in _FRIENDLY_ERRORS:
        if isinstance(exc, exc_type):
            return f"❌ {msg}"
    return f"❌ Er is een fout opgetreden: {exc}"


async def _setup_modes() -> None:
    modus_mode = cl.Mode(
        id="modus",
        name="Modus",
        options=[
            cl.ModeOption(id="snel", name="Snel", description="Precies het gevraagde, niet meer", icon="zap", default=True),
            cl.ModeOption(id="verdiep", name="Verdiep", description="Doorvragen + volledige analyse", icon="microscope"),
        ],
    )

    modes = [modus_mode]

    available = get_available_models()
    if available:
        model_options = [
            cl.ModeOption(
                id=mid,
                name=name,
                description=desc,
                icon=icon,
                default=(mid == MODEL),
            )
            for mid, name, desc, icon in available
        ]
        if not any(o.default for o in model_options):
            model_options[0].default = True
        modes.insert(0, cl.Mode(id="model", name="Model", options=model_options))

    await cl.context.emitter.set_modes(modes)


async def _set_thread_title(question: str, answer: str, model: str | None = None) -> None:
    try:
        title = await generate_title(question, answer, model=model)
        layer = get_data_layer()
        if layer:
            await layer.update_thread(
                thread_id=cl.context.session.thread_id,
                name=title,
            )
        await cl.context.emitter.emit(
            "first_interaction",
            {"interaction": title, "thread_id": cl.context.session.thread_id},
        )
    except Exception:
        pass


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label="MBO studenten 2023", message="Hoeveel MBO studenten waren er in 2023?"),
        cl.Starter(label="HBO-instellingen Amsterdam", message="Welke HBO-instellingen zijn er in Amsterdam?"),
        cl.Starter(label="WO uitstroom man/vrouw", message="Wat is het verschil in uitstroom tussen mannen en vrouwen in het WO?"),
        cl.Starter(label="VMBO instroom trend", message="Toon de trend in VMBO instroom over de afgelopen 10 jaar."),
    ]


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    messages = build_messages_from_thread(thread)
    turns = build_turns_from_thread(thread)
    figures = [fig for turn in turns for fig in turn.get("figures", [])]
    cl.user_session.set("messages", messages)
    cl.user_session.set("turns", turns)
    cl.user_session.set("figures", figures)
    cl.user_session.set("turn_figures", [])
    await _setup_modes()


@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("figures", [])
    cl.user_session.set("turns", [])

    is_ollama = MODEL.startswith("ollama_chat/") or MODEL.startswith("ollama/")
    known_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "AZURE_AI_API_KEY", "GEMINI_API_KEY", "WILLMA_API_KEY"]
    if not is_ollama and not any(os.getenv(k) for k in known_keys):
        await cl.Message(content="⚠️ Geen API key gevonden. Stel een omgevingsvariabele in (bijv. `ANTHROPIC_API_KEY`) en herstart de app.").send()
        return

    await _setup_modes()


@cl.on_stop
async def on_stop():
    stop_event: asyncio.Event | None = cl.user_session.get("stop_event")
    if stop_event:
        stop_event.set()


async def _process_message(content: str, modus: str = "snel", model: str | None = None) -> None:
    messages: list = cl.user_session.get("messages")
    messages.append({"role": "user", "content": content})

    stop_event = asyncio.Event()
    cl.user_session.set("stop_event", stop_event)
    cl.user_session.set("turn_figures", [])

    try:
        response_text = await run(messages, stop_event, model=model, modus=modus)
    except Exception as e:
        await cl.Message(content=_friendly_error(e)).send()
        return

    messages.append({"role": "assistant", "content": response_text})
    cl.user_session.set("messages", messages)

    turn_figures = cl.user_session.get("turn_figures", [])
    turns: list = cl.user_session.get("turns", [])
    turns.append({"question": content, "answer": response_text, "figures": turn_figures})
    cl.user_session.set("turns", turns)

    if len(messages) == 2:
        asyncio.create_task(_set_thread_title(content, response_text, model=model))


_MAX_UPLOAD_ROWS = 200


async def _read_file_content(el) -> str | None:
    path = el.path
    if not path:
        return None
    name = el.name or os.path.basename(path)
    lower = name.lower()

    try:
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True, data_only=True)
            parts = []
            for ws in wb.worksheets:
                rows = list(ws.iter_rows(values_only=True))
                if not rows:
                    continue
                header = [str(c) if c is not None else "" for c in rows[0]]
                data_rows = rows[1:_MAX_UPLOAD_ROWS + 1]
                lines = ["|".join(header)]
                lines.append("|".join("---" for _ in header))
                for row in data_rows:
                    lines.append("|".join(str(c) if c is not None else "" for c in row))
                label = f"**Sheet: {ws.title}**\n" if len(wb.worksheets) > 1 else ""
                truncated = f"\n\n(... afgekapt na {_MAX_UPLOAD_ROWS} rijen)" if len(rows) - 1 > _MAX_UPLOAD_ROWS else ""
                parts.append(f"{label}{chr(10).join(lines)}{truncated}")
            wb.close()
            return f"\n\n📎 **{name}**\n\n" + "\n\n".join(parts) if parts else None

        if lower.endswith(".csv"):
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = []
                for i, row in enumerate(reader):
                    if i > _MAX_UPLOAD_ROWS:
                        break
                    rows.append(row)
            if not rows:
                return None
            header = rows[0]
            lines = ["|".join(header)]
            lines.append("|".join("---" for _ in header))
            for row in rows[1:]:
                lines.append("|".join(row))
            truncated = f"\n\n(... afgekapt na {_MAX_UPLOAD_ROWS} rijen)" if len(rows) > _MAX_UPLOAD_ROWS else ""
            return f"\n\n📎 **{name}**\n\n{chr(10).join(lines)}{truncated}"

    except Exception:
        return f"\n\n📎 **{name}** — kon niet worden gelezen."

    return None


@cl.on_message
async def on_message(message: cl.Message):
    modus = message.modes.get("modus", "snel") if message.modes else "snel"
    model = message.modes.get("model") if message.modes else None

    content = message.content
    if message.elements:
        for el in message.elements:
            file_text = await _read_file_content(el)
            if file_text:
                content += file_text

    await _process_message(content, modus=modus, model=model)


@cl.action_callback("followup")
async def on_followup(action: cl.Action):
    await cl.context.emitter.send_window_message({
        "type": "set_input",
        "value": action.payload["question"],
    })


@cl.action_callback("download_rapport")
async def on_download_rapport(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    html = generate_report(turns)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        path = f.name

    await cl.Message(
        content="Rapport klaar!",
        elements=[cl.File(name=f"rapport-{date.today()}.html", path=path, mime="text/html")],
    ).send()


@cl.action_callback("download_rapport_pdf")
async def on_download_rapport_pdf(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    pdf_bytes = await asyncio.to_thread(generate_pdf, turns)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        path = f.name

    await cl.Message(
        content="PDF rapport klaar!",
        elements=[cl.File(name=f"rapport-{date.today()}.pdf", path=path, mime="application/pdf")],
    ).send()

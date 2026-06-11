import asyncio
import io
import os
import re
import tempfile
import zipfile
from datetime import date

import chainlit as cl

from config import MODEL
from report import generate_pdf, generate_report
from tools.codegen import build_package


@cl.action_callback("download_rapport")
async def on_download_rapport(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    html = generate_report(turns)
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
            f.write(html)
            path = f.name
        await cl.Message(
            content="Rapport klaar!",
            elements=[cl.File(name=f"rapport-{date.today()}.html", path=path, mime="text/html")],
        ).send()
    finally:
        if path:
            os.unlink(path)


@cl.action_callback("download_rapport_pdf")
async def on_download_rapport_pdf(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    pdf_bytes = await asyncio.to_thread(generate_pdf, turns)
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            path = f.name
        await cl.Message(
            content="PDF rapport klaar!",
            elements=[cl.File(name=f"rapport-{date.today()}.pdf", path=path, mime="application/pdf")],
        ).send()
    finally:
        if path:
            os.unlink(path)


@cl.action_callback("download_python")
async def on_download_python(action: cl.Action):
    from agent import litellm_kwargs
    turns = cl.user_session.get("turns", [])
    thread_id = cl.context.session.thread_id or "chat"
    model = cl.user_session.get("current_model") or MODEL

    await cl.Message(content="⏳ Reproduceerbare code wordt gegenereerd...").send()

    files = await build_package(turns, thread_id, model=model, extra_litellm_kwargs=litellm_kwargs(model))

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    zip_buf.seek(0)

    thread_title = cl.user_session.get("thread_title") or ""
    safe_title = re.sub(r"[^\w\s-]", "", thread_title).strip().replace(" ", "-")[:40]
    title_part = f"-{safe_title}" if safe_title else ""
    zip_name = f"analyse{title_part}-{date.today()}-{thread_id[:8]}.zip"

    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(zip_buf.read())
            path = f.name
        await cl.Message(
            content="Reproduceerbare code klaar!",
            elements=[cl.File(name=zip_name, path=path, mime="application/zip")],
        ).send()
    finally:
        if path:
            os.unlink(path)

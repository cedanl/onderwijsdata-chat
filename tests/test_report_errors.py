import asyncio

from routes import chat


def _run_report(monkeypatch, exc: Exception) -> list[dict]:
    async def failing_generate(*args, **kwargs):
        raise exc

    monkeypatch.setattr(chat, "generate_report_spec", failing_generate)
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    asyncio.run(chat._generate_report({"username": "u"}, emit, model=None))
    return events


def test_unexpected_report_error_hides_exception_text(monkeypatch):
    events = _run_report(monkeypatch, TypeError("unhashable type: 'dict'"))
    [error] = [e for e in events if e["type"] == "report_error"]
    assert "unhashable" not in error["message"]
    assert "Rapport kon niet worden gemaakt" in error["message"]


def test_expected_report_error_keeps_its_guidance(monkeypatch):
    msg = "Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald."
    events = _run_report(monkeypatch, ValueError(msg))
    [error] = [e for e in events if e["type"] == "report_error"]
    assert error["message"] == msg

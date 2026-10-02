"""Hoogstens één clarify per vraag, in code (#75).

"Hoeveel studenten RUG?" kreeg een scopevraag en na het antwoord daarop nog een, terwijl
"meest recente" al gekozen was. De prompt vraagt om één; hier staat dat het niet anders kan.
"""

import asyncio

from agent.run import tools_for
from routes import chat


def _names(session: dict) -> set[str]:
    return {t["function"]["name"] for t in tools_for(session)}


def test_a_new_question_may_ask_for_clarification():
    assert "clarify_scope" in _names({})
    assert "clarify_scope" in _names({"clarify_rondes": 0})


def test_after_an_answered_clarification_the_tool_is_gone():
    names = _names({"clarify_rondes": 1})
    assert "clarify_scope" not in names
    assert "search_catalog" in names  # the rest stays available


def _run(handler, *args):
    async def scenario():
        async def noop(*a, **k):
            return None

        original = chat._process_message
        chat._process_message = noop
        try:
            task = await handler(*args)
            await task
        finally:
            chat._process_message = original

    asyncio.run(scenario())


def _emit(event):
    raise AssertionError(event)


def test_a_clarification_choice_counts_as_a_round_and_a_new_question_resets_it():
    session = chat._new_session()

    _run(chat._handle_clarification, {"choice": "2024/2025"}, session, _emit, None)
    assert session["clarify_rondes"] == 1

    _run(chat._handle_message, {"content": "Hoeveel studenten heeft de RUG?"}, session, _emit, None)
    assert session["clarify_rondes"] == 0


def test_een_gekozen_optie_blijft_bewaard_tot_een_nieuwe_vraag():
    """De keuze is afbakening, geen losse tekst in het gesprek (#246)."""
    session = chat._new_session()

    _run(chat._handle_clarification, {"choice": "2023 (laatste werkelijke cijfers)"}, session, _emit, None)
    assert session["clarify_keuzes"] == ["2023 (laatste werkelijke cijfers)"]

    _run(chat._handle_message, {"content": "Hoeveel studenten heeft de RUG?"}, session, _emit, None)
    assert session["clarify_keuzes"] == []

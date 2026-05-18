from resume import build_messages_from_thread


def test_empty_thread_returns_empty_list():
    assert build_messages_from_thread({"steps": []}) == []


def test_thread_missing_steps_key():
    assert build_messages_from_thread({}) == []


def test_user_and_assistant_messages():
    thread = {
        "steps": [
            {"type": "user_message", "output": "Hallo", "createdAt": "2024-01-01T00:00:00"},
            {"type": "assistant_message", "output": "Hoi!", "createdAt": "2024-01-01T00:00:01"},
        ]
    }
    assert build_messages_from_thread(thread) == [
        {"role": "user", "content": "Hallo"},
        {"role": "assistant", "content": "Hoi!"},
    ]


def test_tool_steps_are_skipped():
    thread = {
        "steps": [
            {"type": "user_message", "output": "Vraag?", "createdAt": "2024-01-01T00:00:00"},
            {"type": "tool", "output": "tool resultaat", "createdAt": "2024-01-01T00:00:01"},
            {"type": "assistant_message", "output": "Antwoord", "createdAt": "2024-01-01T00:00:02"},
        ]
    }
    assert build_messages_from_thread(thread) == [
        {"role": "user", "content": "Vraag?"},
        {"role": "assistant", "content": "Antwoord"},
    ]


def test_run_steps_are_skipped():
    thread = {
        "steps": [
            {"type": "user_message", "output": "Vraag?", "createdAt": "2024-01-01T00:00:00"},
            {"type": "run", "output": "intern resultaat", "createdAt": "2024-01-01T00:00:01"},
            {"type": "assistant_message", "output": "Antwoord", "createdAt": "2024-01-01T00:00:02"},
        ]
    }
    assert build_messages_from_thread(thread) == [
        {"role": "user", "content": "Vraag?"},
        {"role": "assistant", "content": "Antwoord"},
    ]


def test_empty_output_steps_are_excluded():
    thread = {
        "steps": [
            {"type": "user_message", "output": "Vraag?", "createdAt": "2024-01-01T00:00:00"},
            {"type": "assistant_message", "output": "", "createdAt": "2024-01-01T00:00:01"},
            {"type": "assistant_message", "output": "Echt antwoord", "createdAt": "2024-01-01T00:00:02"},
        ]
    }
    assert build_messages_from_thread(thread) == [
        {"role": "user", "content": "Vraag?"},
        {"role": "assistant", "content": "Echt antwoord"},
    ]


def test_none_output_steps_are_excluded():
    thread = {
        "steps": [
            {"type": "user_message", "output": None, "createdAt": "2024-01-01T00:00:00"},
            {"type": "assistant_message", "output": "Antwoord", "createdAt": "2024-01-01T00:00:01"},
        ]
    }
    assert build_messages_from_thread(thread) == [
        {"role": "assistant", "content": "Antwoord"},
    ]


def test_multiple_turns():
    thread = {
        "steps": [
            {"type": "user_message", "output": "Vraag 1", "createdAt": "2024-01-01T00:00:00"},
            {"type": "assistant_message", "output": "Antwoord 1", "createdAt": "2024-01-01T00:00:01"},
            {"type": "user_message", "output": "Vraag 2", "createdAt": "2024-01-01T00:01:00"},
            {"type": "assistant_message", "output": "Antwoord 2", "createdAt": "2024-01-01T00:01:01"},
        ]
    }
    assert build_messages_from_thread(thread) == [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Antwoord 1"},
        {"role": "user", "content": "Vraag 2"},
        {"role": "assistant", "content": "Antwoord 2"},
    ]

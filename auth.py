import os
from typing import Optional

import chainlit as cl


def parse_users(users_env: str) -> dict[str, str]:
    """Parse 'user:pass,user2:pass2' env var into a dict."""
    if not users_env.strip():
        return {}
    result = {}
    for entry in users_env.split(","):
        entry = entry.strip()
        if ":" in entry:
            user, _, password = entry.partition(":")
            result[user.strip()] = password.strip()
    return result


def check_credentials(username: str, password: str, users: dict[str, str]) -> bool:
    return username in users and users[username] == password


_USERS = parse_users(os.getenv("CHAT_USERS", ""))


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    if check_credentials(username, password, _USERS):
        return cl.User(identifier=username, metadata={"role": "user", "provider": "credentials"})
    return None


@cl.header_auth_callback
def header_auth_callback(headers: dict) -> Optional[cl.User]:
    secret = os.getenv("CHAT_HEADER_SECRET")
    if secret and headers.get("X-Chat-Secret") == secret:
        identifier = headers.get("X-Chat-User", "user")
        return cl.User(identifier=identifier, metadata={"role": "user", "provider": "header"})
    return None

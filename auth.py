import hmac
import os

_AUTH_ENABLED = bool(os.getenv("CHAT_USERS"))


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
    stored = users.get(username)
    if stored is None:
        return False
    return hmac.compare_digest(stored, password)


USERS = parse_users(os.getenv("CHAT_USERS", ""))
AUTH_ENABLED = bool(USERS)

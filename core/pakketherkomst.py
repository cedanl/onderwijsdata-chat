"""Waar de bronpakketten vandaan komen en hoe je ze installeert (#888).

`onderwijsbronnen` (tot #910 `onderwijsdata` en `riodata`) is sinds #885 lid van de uv-workspace onder `packages/` en
staat niet op PyPI. Zijn metadata heeft daarom geen git-commit meer (`direct_url.json` zonder `vcs_info`): het pakket
komt uit dezelfde commit als de app. Herleidbaar is een pakket dus via het versienummer plus de commit van de chat-repo waaruit het image is
gebouwd (`GIT_COMMIT`, #231).

Installeren kan alleen uit die repo. De publieke GitHub-spiegel heeft dezelfde commits als GitLab `main` (Agents.md),
dus `pip install "<pakket> @ git+<spiegel>@<commit>#subdirectory=packages/<pakket>"` geeft precies de pakketcode waarop
de app draaide (besluit #884). Dit is de enige plek die dat adres en die map kent.
"""

from importlib import metadata

# De publieke spiegel van deze repo; de oude pakketrepo's (cbs-/rio-onderwijsdata) zijn alleen nog archief.
SPIEGEL_URL = "https://github.com/cedanl/onderwijsdata-chat"
PAKKETMAP = "packages"


def pakketversie(naam: str) -> str | None:
    """Versienummer van het geïnstalleerde pakket; None als het niet geïnstalleerd is."""
    try:
        return metadata.version(naam)
    except metadata.PackageNotFoundError:
        return None


def installatiespec(naam: str, commit: str | None) -> str:
    """PEP 508-regel die het pakket uit de spiegel installeert, op `commit` (zonder commit: de nieuwste main)."""
    revisie = f"@{commit}" if commit else ""
    return f"{naam} @ git+{SPIEGEL_URL}{revisie}#subdirectory={PAKKETMAP}/{naam}"

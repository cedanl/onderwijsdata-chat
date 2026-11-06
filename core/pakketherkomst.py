"""Waar de bronpakketten vandaan komen en hoe je ze installeert (#888).

`onderwijsbronnen` (tot #910 `onderwijsdata` en `riodata`) is sinds #885 lid van de uv-workspace onder `packages/` en
staat niet op PyPI. Zijn metadata heeft daarom geen git-commit meer (`direct_url.json` zonder `vcs_info`): het pakket
komt uit dezelfde commit als de app. Herleidbaar is een pakket dus via het versienummer plus de commit van de chat-repo waaruit het image is
gebouwd (`GIT_COMMIT`, #231).

Installeren kan alleen uit die repo. De publieke GitHub-spiegel heeft dezelfde commits als GitLab `main` (Agents.md),
dus `pip install "<pakket> @ git+<spiegel>@<commit>#subdirectory=packages/<pakket>"` geeft precies de pakketcode waarop
de app draaide (besluit #884). Dit is de enige plek die dat adres en die map kent.

Het pakket zelf vraagt alleen httpx en defusedxml; pandas en openpyxl zijn extras. Een snippet leest elke lading als
DataFrame, en de financiën van DUO (#935) en de crebolijst van SBB lezen Excel: zonder extras faalde de regel bij de
eerste `load` (#971). Wie de regel maakt, noemt daarom de extras die de code ernaast nodig heeft.
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


def installatiespec(naam: str, commit: str | None, extras: tuple[str, ...] = ()) -> str:
    """PEP 508-regel die het pakket met `extras` uit de spiegel installeert, op `commit` (zonder commit: de nieuwste
    main)."""
    revisie = f"@{commit}" if commit else ""
    met = f"[{','.join(extras)}]" if extras else ""
    return f"{naam}{met} @ git+{SPIEGEL_URL}{revisie}#subdirectory={PAKKETMAP}/{naam}"

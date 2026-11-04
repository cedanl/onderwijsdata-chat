#!/usr/bin/env python
"""
De bot van de geplande pakketjobs (#887): wijzigingen als MR met auto-merge, bevindingen als één open issue.

Gebruik (in CI, zie .gitlab-ci.yml en docs/operatie.md "Bronpakketten bijhouden"):
    python scripts/pakketbot.py controleer
        # het token bestaat en werkt; exit 2 zonder token, 1 bij een geweigerd token
    python scripts/pakketbot.py mr --branch bot/<naam> --titel "chore(...): ..." PAD [PAD ...]
        # wijzigingen onder de paden → commit op bot/<naam> (force) → MR naar main met auto-merge
    python scripts/pakketbot.py meld-discovery --rapport packages/onderwijsdata/data/03-output/cbs_discovery.json
    python scripts/pakketbot.py meld-broncontrole --meldingen meldingen.txt --code <exitcode van broncontrole.py>

In de oude pakketrepo's pushten de GitHub Actions zelf op main en maakte de broncontrole elke week een nieuw issue.
Hier gaat een wijziging door een MR (review en de volle pipeline), en een bevinding staat in één open issue per
controle: bestaat dat al, dan krijgt het alleen een notitie als de stand veranderde.

Het token komt uit de CI-variabele PAKKETBOT_TOKEN (masked en protected): een projecttoken met rol Developer en de
scopes `api` en `write_repository`. Het script print het nooit; git krijgt het via een credential helper die het
uit de omgeving leest, niet op de opdrachtregel of in een URL.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx

TOKEN_VAR = "PAKKETBOT_TOKEN"
TOKEN_UITLEG = (
    f"{TOKEN_VAR} ontbreekt. Maak een projecttoken (Settings → Access tokens, rol Developer, scopes api en "
    f"write_repository) en zet het als CI/CD-variabele {TOKEN_VAR}, masked en protected (docs/operatie.md, "
    f'"Bronpakketten bijhouden").'
)
BOT_NAAM = "onderwijsdata-pakketbot"
BOT_EMAIL = "noreply@git.ia.surf.nl"
MR_LABELS = "data,type::chore"
ISSUE_LABELS = "data"
# Wat na de kern van een issuebeschrijving komt (job, pipeline) verschilt per run en telt niet mee bij vergelijken.
VOET = "<!-- pakketbot -->"
DISCOVERY_TITEL = "Discovery: nieuwe CBS-tabellen ter review"
BRONCONTROLE_TITEL = "Broncontrole: review nodig (DUO CKAN en RIO)"
DISCOVERY_MAX = 50
# Pipelinestatussen waarin auto-merge zin heeft: de pipeline van de gepushte commit loopt nog.
LOPEND = {"created", "waiting_for_resource", "preparing", "pending", "running"}
MISLUKT = {"failed"}  # niet "canceled": een nieuwere pipeline breekt een oudere soms af (auto-cancel)


class BotFout(Exception):
    """Een fout met een melding voor de log; de exitcode staat erbij."""

    def __init__(self, melding: str, code: int = 1):
        super().__init__(melding)
        self.code = code


# --- GitLab ---------------------------------------------------------------------------------


def token(env: Mapping[str, str]) -> str:
    waarde = env.get(TOKEN_VAR, "").strip()
    if not waarde:
        raise BotFout(TOKEN_UITLEG, code=2)
    return waarde


def gitlab(env: Mapping[str, str], transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Client op /projects/<id> van dit project, met het bottoken."""
    geheim = token(env)
    for var in ("CI_API_V4_URL", "CI_PROJECT_ID"):
        if not env.get(var):
            raise BotFout(f"{var} ontbreekt: dit script draait in een GitLab-job.", code=2)
    return httpx.Client(
        base_url=f"{env['CI_API_V4_URL']}/projects/{env['CI_PROJECT_ID']}/",
        headers={"PRIVATE-TOKEN": geheim},
        timeout=30,
        transport=transport,
    )


def _antwoord(r: httpx.Response, wat: str) -> httpx.Response:
    if r.status_code in (401, 403):
        raise BotFout(
            f"GitLab weigert het token bij {wat} (HTTP {r.status_code}): controleer rol en scopes van {TOKEN_VAR}."
        )
    if r.is_error:
        raise BotFout(f"GitLab gaf HTTP {r.status_code} bij {wat}: {r.text[:300]}")
    return r


def controleer(gl: httpx.Client) -> str:
    project = _antwoord(gl.get(""), "het project lezen").json()
    return project["path_with_namespace"]


def voet(env: Mapping[str, str]) -> str:
    job = env.get("CI_JOB_NAME", "?")
    url = env.get("CI_PIPELINE_URL", "")
    return f'{VOET}\n_Gemaakt door de geplande job `{job}` ({url}); zie docs/operatie.md, "Bronpakketten bijhouden"._'


# --- issues ---------------------------------------------------------------------------------


def _kern(beschrijving: str) -> str:
    return beschrijving.split(VOET, 1)[0].strip()


def open_issue(gl: httpx.Client, titel: str) -> dict | None:
    r = _antwoord(
        gl.get("issues", params={"state": "opened", "in": "title", "search": titel, "per_page": 100}), "issues zoeken"
    )
    return next((i for i in r.json() if i["title"] == titel), None)


def issue_bijwerken(gl: httpx.Client, titel: str, kern: str, env: Mapping[str, str], datum: str) -> str:
    """Eén open issue per titel: aanmaken, of bij een andere stand de beschrijving vervangen en een notitie zetten."""
    beschrijving = f"{kern.strip()}\n\n{voet(env)}"
    bestaand = open_issue(gl, titel)
    if bestaand is None:
        nieuw = _antwoord(
            gl.post("issues", json={"title": titel, "description": beschrijving, "labels": ISSUE_LABELS}),
            "issue aanmaken",
        ).json()
        return f"nieuw issue #{nieuw['iid']}: {nieuw['web_url']}"
    iid = bestaand["iid"]
    if _kern(bestaand.get("description") or "") == kern.strip():
        return f"issue #{iid} bestaat al met dezelfde stand; niets gewijzigd"
    _antwoord(gl.put(f"issues/{iid}", json={"description": beschrijving}), "issue bijwerken")
    notitie = f"Nieuwe stand op {datum} (de beschrijving is vervangen):\n\n{kern.strip()}"
    _antwoord(gl.post(f"issues/{iid}/notes", json={"body": notitie}), "notitie zetten")
    return f"issue #{iid} bijgewerkt met de nieuwe stand: {bestaand['web_url']}"


def discovery_tekst(rapport: dict) -> str | None:
    """De issuetekst van de CBS-discovery, of None als er niets ter review is (zelfde tekst als de oude workflow)."""
    s = rapport["samenvatting"]
    if not s["nieuw_voor_review"]:
        return None
    regels = [
        f"{s['nieuw_voor_review']} nieuwe tabel(len) onder onderwijsthema's, nog niet in de catalogus "
        f"(actief {s['nieuw_voor_review_actief']}, historisch {s['nieuw_voor_review_historisch']}).",
        "",
        "Scope: alleen mbo/hbo/wo. Beoordeel per tabel; niets is automatisch toegevoegd.",
        "",
    ]
    regels += [
        f"- `{n['dataset_id']}` {n['titel']} ({n['classificatie']}; {n['thema']})"
        for n in rapport["nieuw_voor_review"][:DISCOVERY_MAX]
    ]
    return "\n".join(regels)


def broncontrole_tekst(meldingen: str) -> str:
    regels = [r for r in meldingen.splitlines() if r.strip()]
    kop = (
        "De wekelijkse broncontrole van riodata (`packages/riodata/catalogus/broncontrole.py`) vergelijkt DUO CKAN en "
        "de RIO-spec met de catalogus. De catalogus is niet aangepast; beoordeel per melding."
    )
    return "\n".join([kop, "", *(f"- {r}" for r in regels)])


# --- MR -------------------------------------------------------------------------------------

Run = Callable[..., subprocess.CompletedProcess]


def _git(run: Run, *args: str, env: Mapping[str, str] | None = None) -> str:
    uit = run(["git", *args], capture_output=True, text=True, env=dict(env) if env is not None else None)
    if uit.returncode != 0:
        raise BotFout(f"git {args[0]} faalde: {uit.stderr.strip()[:500]}")
    return uit.stdout


def gewijzigde_paden(paden: list[str], run: Run = subprocess.run) -> list[str]:
    """Gewijzigde, nieuwe en verwijderde bestanden onder de paden, volgens git status."""
    uit = _git(run, "status", "--porcelain", "--untracked-files=all", "--", *paden)
    return sorted(regel[3:] for regel in uit.splitlines() if regel.strip())


def push_url(env: Mapping[str, str]) -> str:
    return f"{env['CI_SERVER_URL']}/{env['CI_PROJECT_PATH']}.git"


# Git vraagt de helper om gebruiker en wachtwoord; de helper leest het token uit de omgeving van het git-proces.
CREDENTIAL_HELPER = f'!f() {{ echo username=oauth2; echo "password=${{{TOKEN_VAR}}}"; }}; f'


def commit_en_push(
    branch: str, bericht: str, paden: list[str], url: str, env: Mapping[str, str], run: Run = subprocess.run
) -> str:
    """Commit de paden op een verse branch vanaf HEAD en push die met force; geeft de commit-sha terug."""
    _git(run, "checkout", "-B", branch)
    _git(run, "add", "--all", "--", *paden)
    _git(run, "-c", f"user.name={BOT_NAAM}", "-c", f"user.email={BOT_EMAIL}", "commit", "--quiet", "-m", bericht)
    sha = _git(run, "rev-parse", "HEAD").strip()
    git_env = {**os.environ, **env, "GIT_TERMINAL_PROMPT": "0"}
    _git(
        run,
        "-c",
        f"credential.helper={CREDENTIAL_HELPER}",
        "push",
        "--force",
        "--quiet",
        url,
        f"HEAD:refs/heads/{branch}",
        env=git_env,
    )
    return sha


def mr_openen(gl: httpx.Client, branch: str, titel: str, beschrijving: str, doel: str) -> dict:
    """De open MR van de botbranch, of een nieuwe; een bestaande krijgt de nieuwe titel en beschrijving."""
    r = _antwoord(
        gl.get("merge_requests", params={"state": "opened", "source_branch": branch, "target_branch": doel}),
        "MR's zoeken",
    )
    bestaand = r.json()
    if bestaand:
        iid = bestaand[0]["iid"]
        return _antwoord(
            gl.put(f"merge_requests/{iid}", json={"title": titel, "description": beschrijving}), "MR bijwerken"
        ).json()
    velden = {
        "source_branch": branch,
        "target_branch": doel,
        "title": titel,
        "description": beschrijving,
        "labels": MR_LABELS,
        "remove_source_branch": True,
    }
    return _antwoord(gl.post("merge_requests", json=velden), "MR aanmaken").json()


def auto_merge(
    gl: httpx.Client, iid: int, sha: str, wacht: Callable[[float], None] = time.sleep, pogingen: int = 60
) -> bool:
    """Zet auto-merge zodra de pipeline van de gepushte commit loopt; True als GitLab het bevestigt.

    Direct na het aanmaken geeft PUT .../merge een 405 zolang de MR-pipeline er niet is, en een push zet auto-merge
    terug. Daarom: wachten tot de MR op de gepushte sha staat met een lopende pipeline, dan pas de PUT (met `sha`, zodat
    GitLab niets anders merget dan wat hier gepusht is), en daarna nalezen.
    """
    for _ in range(pogingen):
        mr = _antwoord(gl.get(f"merge_requests/{iid}"), "MR lezen").json()
        if mr.get("state") == "merged" or (mr.get("merge_when_pipeline_succeeds") and mr.get("sha") == sha):
            return True
        pipeline = mr.get("head_pipeline") or {}
        if mr.get("sha") == sha and pipeline.get("status") in MISLUKT:
            raise BotFout(f"De pipeline van MR !{iid} is {pipeline['status']}: {pipeline.get('web_url', '')}")
        if mr.get("sha") == sha and pipeline.get("status") in LOPEND:
            r = gl.put(
                f"merge_requests/{iid}/merge",
                data={"auto_merge": "true", "should_remove_source_branch": "true", "sha": sha},
            )
            if r.status_code in (401, 403):
                _antwoord(r, "auto-merge zetten")
        wacht(10)
    return False


def mr_beschrijving(gewijzigd: list[str], toelichting: str, env: Mapping[str, str]) -> str:
    bestanden = "\n".join(f"- `{p}`" for p in gewijzigd[:100])
    meer = f"\n- … en {len(gewijzigd) - 100} meer" if len(gewijzigd) > 100 else ""
    return (
        f"{toelichting.strip()}\n\n"
        f"Gewijzigde bestanden ({len(gewijzigd)}):\n{bestanden}{meer}\n\n"
        "Gemaakt door een geplande job; een volgende run schrijft deze branch opnieuw vanaf main. "
        "Auto-merge staat aan: na goedkeuring en een groene pipeline gaat dit vanzelf naar main.\n\n"
        f"{voet(env)}"
    )


# --- subcommando's --------------------------------------------------------------------------


def cmd_mr(
    args: argparse.Namespace, env: Mapping[str, str], gl: httpx.Client, run: Run = subprocess.run, wacht=time.sleep
) -> str:
    gewijzigd = gewijzigde_paden(args.paden, run)
    if not gewijzigd:
        return "Geen wijzigingen onder " + ", ".join(args.paden) + "; geen MR."
    doel = env.get("CI_DEFAULT_BRANCH", "main")
    bericht = f"{args.titel}\n\nGemaakt door de geplande job {env.get('CI_JOB_NAME', '?')}: {env.get('CI_JOB_URL', '')}"
    sha = commit_en_push(args.branch, bericht, args.paden, push_url(env), env, run)
    mr = mr_openen(gl, args.branch, args.titel, mr_beschrijving(gewijzigd, args.toelichting, env), doel)
    if not auto_merge(gl, mr["iid"], sha, wacht):
        raise BotFout(
            f"MR !{mr['iid']} staat open, maar auto-merge kwam niet aan: zet het met de hand ({mr['web_url']})."
        )
    return f"MR !{mr['iid']} met {len(gewijzigd)} bestanden, auto-merge aan: {mr['web_url']}"


def cmd_meld_discovery(args: argparse.Namespace, env: Mapping[str, str], gl: httpx.Client) -> str:
    tekst = discovery_tekst(json.loads(Path(args.rapport).read_text(encoding="utf-8")))
    if tekst is None:
        return "Geen nieuwe CBS-tabellen ter review."
    return issue_bijwerken(gl, DISCOVERY_TITEL, tekst, env, time.strftime("%Y-%m-%d"))


def cmd_meld_broncontrole(args: argparse.Namespace, env: Mapping[str, str], gl: httpx.Client) -> str:
    if args.code == 0:
        return "Broncontrole: niets te melden."
    if args.code != 10:
        raise BotFout(f"Broncontrole mislukt (exitcode {args.code}); het vorige manifest blijft staan.")
    tekst = broncontrole_tekst(Path(args.meldingen).read_text(encoding="utf-8"))
    return issue_bijwerken(gl, BRONCONTROLE_TITEL, tekst, env, time.strftime("%Y-%m-%d"))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    sub = p.add_subparsers(dest="commando", required=True)
    sub.add_parser("controleer", help="het token bestaat en werkt")
    mr = sub.add_parser("mr", help="wijzigingen onder de paden als MR met auto-merge")
    mr.add_argument("--branch", required=True)
    mr.add_argument("--titel", required=True)
    mr.add_argument("--toelichting", default="")
    mr.add_argument("paden", nargs="+")
    d = sub.add_parser("meld-discovery", help="nieuwe CBS-tabellen als issue")
    d.add_argument("--rapport", required=True)
    b = sub.add_parser("meld-broncontrole", help="meldingen van de riodata-broncontrole als issue")
    b.add_argument("--meldingen", required=True)
    b.add_argument("--code", type=int, required=True)
    return p


def main(argv: list[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    args = parser().parse_args(argv)
    try:
        with gitlab(env) as gl:
            if args.commando == "controleer":
                uit = f"{TOKEN_VAR} werkt voor {controleer(gl)}."
            elif args.commando == "mr":
                uit = cmd_mr(args, env, gl)
            elif args.commando == "meld-discovery":
                uit = cmd_meld_discovery(args, env, gl)
            else:
                uit = cmd_meld_broncontrole(args, env, gl)
    except BotFout as fout:
        print(f"FOUT: {fout}", file=sys.stderr)
        return fout.code
    print(uit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Ladder-promotie: `test` volgt main, `playground` staat vast op een release.

    uv run python scripts/promotie.py check               # CI-poort
    uv run python scripts/promotie.py promote             # playground <- nieuwste release-tag
    uv run python scripts/promotie.py promote --version 2.0.0
    uv run python scripts/promotie.py mark                # record: env/playground/<versie>

De pin in `manifests/playground/helmrelease.yaml` ís de deploy: Flux installeert
precies die chartversie. `test` houdt de open range en toont daarmee elke
main-build als eerste.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

MANIFESTS = Path(__file__).resolve().parent.parent / "manifests"
REMOTE = "origin"

RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")
RANGE_RE = re.compile(r"^>=\d+\.\d+\.\d+-\d+(\.\d+)?$")
VERSION_LINE_RE = re.compile(r"(?P<head>  chart:\n    spec:\n(?:.*\n)*?)(?P<line>      version:[^\n]*)\n")


def helmrelease(env: str) -> Path:
    return MANIFESTS / env / "helmrelease.yaml"


def lees_pin(env: str) -> str:
    doc = yaml.safe_load(helmrelease(env).read_text())
    return str(doc["spec"]["chart"]["spec"]["version"])


def schrijf_pin(env: str, versie: str) -> None:
    """Herschrijf alleen de versieregel; commentaar en layout blijven staan."""
    pad = helmrelease(env)
    tekst = pad.read_text()
    blok = VERSION_LINE_RE.search(tekst)
    if not blok:
        raise SystemExit(f"{pad}: spec.chart.spec.version niet gevonden")
    nieuw = tekst[: blok.start("line")] + f'      version: "{versie}"' + tekst[blok.end("line") :]
    pad.write_text(nieuw)


def release_tags(tags: list[str]) -> list[str]:
    """Kale X.Y.Z-tags, oplopend. Alleen die publiceert SDP als schone chart."""
    gevonden = [t for t in tags if RELEASE_RE.match(t)]
    return sorted(gevonden, key=lambda t: tuple(int(d) for d in t.split(".")))


def remote_tags() -> list[str]:
    uit = subprocess.check_output(["git", "ls-remote", "--tags", "--refs", REMOTE], text=True, timeout=60)
    return [regel.split("refs/tags/")[1] for regel in uit.splitlines() if "refs/tags/" in regel]


def fouten(test_pin: str, playground_pin: str, tags: list[str]) -> list[str]:
    """Regels van de ladder; een lege lijst betekent dat alles klopt."""
    gevonden = []
    if not RANGE_RE.match(test_pin):
        gevonden.append(f"test moet de open range houden (>=0.0.1-0.0), staat op {test_pin!r}")
    if not RELEASE_RE.match(playground_pin):
        gevonden.append(f"playground moet een vaste release X.Y.Z pinnen, staat op {playground_pin!r}")
    elif playground_pin not in tags:
        gevonden.append(f"playground pint {playground_pin}, maar die release-tag bestaat niet op {REMOTE}")
    return gevonden


def check() -> int:
    gevonden = fouten(lees_pin("test"), lees_pin("playground"), remote_tags())
    for f in gevonden:
        print(f"FOUT: {f}", file=sys.stderr)
    return 1 if gevonden else 0


def promote(versie: str | None) -> int:
    tags = release_tags(remote_tags())
    if versie is None:
        if not tags:
            raise SystemExit("geen release-tags op de remote om naar te promoveren")
        versie = tags[-1]
    if versie not in tags:
        raise SystemExit(f"{versie!r} is geen bestaande release-tag (kaal X.Y.Z, zonder v)")
    huidig = lees_pin("playground")
    if huidig == versie:
        print(f"playground pint al {versie}")
        return 0
    schrijf_pin("playground", versie)
    print(f"playground: {huidig} -> {versie}")
    print("Volgende stap: branch chore/promote-playground, commit, MR; na merge `mark`.")
    return 0


def mark() -> int:
    versie = lees_pin("playground")
    tag = f"env/playground/{versie}"
    subprocess.check_call(["git", "tag", "-a", tag, "-m", f"playground gepromoveerd naar {versie}"])
    print(f"{tag} aangemaakt; push met: git push {REMOTE} {tag}")
    return 0


def main() -> int:
    ouder = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ouder.add_subparsers(dest="opdracht", required=True)
    sub.add_parser("check")
    p = sub.add_parser("promote")
    p.add_argument("--version")
    sub.add_parser("mark")
    args = ouder.parse_args()
    if args.opdracht == "check":
        return check()
    if args.opdracht == "promote":
        return promote(args.version)
    return mark()


if __name__ == "__main__":
    raise SystemExit(main())

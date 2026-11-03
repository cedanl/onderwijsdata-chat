"""Harbor-onderhoud: het quotum vrijhouden zonder een image weg te halen dat een omgeving gebruikt.

    python scripts/harbor_onderhoud.py status               # quotum, pins, immutability; exit 1 bij een probleem
    python scripts/harbor_onderhoud.py opruimen             # dry-run: wat zou weg, wat blijft en waarom
    python scripts/harbor_onderhoud.py opruimen --uitvoeren # echt verwijderen

Image en chart staan in Harbor-project `ceda-onderwijsdata-chat` (100 GiB). Elke pipeline pusht een image van
~350 MB; het SDP-retentiebeleid houdt elk image 31 dagen vast (de scan na de push telt als pull), dus zonder dit
script loopt het quotum vol en faalt `docker:docker-build` met "will exceed the configured upper limit".

Nooit verwijderd: release-tags (X.Y.Z), `latest`, de chart die elke omgeving in `manifests/<env>/helmrelease.yaml`
volgt (pin of hoogste versie binnen de range, zoals Flux kiest) met het image waar die chart naar wijst, de nieuwste
main- en MR-builds, alles van de laatste uren, en elke tag die het script niet herkent. Kan het script een
omgeving niet herleiden, dan verwijdert het niets.

Werkt met harbor-cli (`harbor login`, zie Agents.md "Harbor-onderhoud") en PyYAML.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

MANIFESTS = Path(__file__).resolve().parent.parent / "manifests"
PROJECT = "ceda-onderwijsdata-chat"
IMAGE_REPO = f"{PROJECT}/onderwijsdata-chat"
CHART_REPO = f"{PROJECT}/onderwijsdata-chat/onderwijsdata-chat"
ENVS = ("development", "test", "playground", "production")

BEHOUD_MAIN = 10  # rollbackruimte voor test: Flux kan op een oudere rc blijven staan als de nieuwste faalt
BEHOUD_MR = 20  # development en lopende MR-pipelines
MIN_UREN = 24  # niets van een pipeline die mogelijk nog loopt
QUOTUM_DREMPEL = 0.8

RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CIJFERS = "{[0-9],[0-9][0-9],[0-9][0-9][0-9]}"
IMMUTABLE_PATROON = f"{_CIJFERS}.{_CIJFERS}.{_CIJFERS}"  # doublestar in Harbor; alleen cijfers, geen * (Agents.md)
SHA_RE = re.compile(r"^[0-9a-f]{8}$")
# Helm zet de build-metadata (+sha) in een OCI-tag om naar _: main = X.Y.Z-rc.N_<sha>, MR = 0.0.1-build.N_<slug>.<sha>.
MAIN_CHART_RE = re.compile(r"^\d+\.\d+\.\d+-rc\.\d+_(?P<sha>[0-9a-f]{8})$")
MR_CHART_RE = re.compile(r"^\d+\.\d+\.\d+-build\.\d+_[a-z0-9]+\.(?P<sha>[0-9a-f]{8})$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
RANGE_RE = re.compile(r"^>=\s*(\S+)$")


@dataclass(frozen=True)
class Artifact:
    digest: str
    tags: tuple[str, ...]
    push_time: datetime
    size: int


@dataclass
class Plan:
    weg_images: list[Artifact] = field(default_factory=list)
    weg_charts: list[Artifact] = field(default_factory=list)
    beschermd: dict[str, str] = field(default_factory=dict)  # tag -> reden
    omgevingen: dict[str, tuple[str, str]] = field(default_factory=dict)  # env -> (chart, image)
    fouten: list[str] = field(default_factory=list)


# --- semver zoals Flux (Masterminds) een chartversie vergelijkt ---------------------------------------------------


def semver_sleutel(versie: str) -> tuple:
    """Sorteersleutel volgens SemVer 2.0: prerelease vóór de release, numerieke delen numeriek, build telt niet."""
    m = SEMVER_RE.match(versie.replace("_", "+"))
    if not m:
        raise ValueError(f"geen semver: {versie!r}")
    kern = tuple(int(d) for d in m.group(1, 2, 3))
    pre = m.group(4)
    if pre is None:
        return (kern, 1, ())
    delen = tuple((0, int(d), "") if d.isdigit() else (1, 0, d) for d in pre.split("."))
    return (kern, 0, delen)


def hoogste_in_range(tags: list[str], bereik: str) -> str | None:
    """Hoogste chart-tag die aan `>=X.Y.Z-pre` voldoet (met prerelease erin, zoals de range dat opent)."""
    m = RANGE_RE.match(bereik)
    if not m:
        raise ValueError(f"range {bereik!r} niet ondersteund (alleen >=X.Y.Z-pre)")
    ondergrens = semver_sleutel(m.group(1))
    kandidaten = []
    for t in tags:
        try:
            sleutel = semver_sleutel(t)
        except ValueError:
            continue
        if sleutel >= ondergrens:
            kandidaten.append((sleutel, t))
    return max(kandidaten)[1] if kandidaten else None


def chart_sha(tag: str) -> str | None:
    m = MAIN_CHART_RE.match(tag) or MR_CHART_RE.match(tag)
    return m.group("sha") if m else None


# --- het plan (puur, zonder Harbor) ------------------------------------------------------------------------------


def lees_pins(manifests: Path = MANIFESTS) -> dict[str, str]:
    pins = {}
    for env in ENVS:
        pad = manifests / env / "helmrelease.yaml"
        if pad.exists():
            pins[env] = str(yaml.safe_load(pad.read_text())["spec"]["chart"]["spec"]["version"])
    return pins


def maak_plan(
    images: list[Artifact],
    charts: list[Artifact],
    pins: dict[str, str],
    nu: datetime,
    behoud_main: int = BEHOUD_MAIN,
    behoud_mr: int = BEHOUD_MR,
    min_uren: int = MIN_UREN,
) -> Plan:
    plan = Plan()
    chart_tags = [t for a in charts for t in a.tags]
    image_tags = {t for a in images for t in a.tags}
    main_shas = {s for t in chart_tags if MAIN_CHART_RE.match(t) and (s := chart_sha(t))}
    grens = nu - timedelta(hours=min_uren)

    # 1. Wat elke omgeving volgt: de pin of de hoogste chart binnen de range, en het image daarachter.
    for env, versie in sorted(pins.items()):
        if RELEASE_RE.match(versie):
            gekozen, image_tag = versie, versie
        else:
            try:
                gekozen = hoogste_in_range(chart_tags, versie)
            except ValueError as e:
                plan.fouten.append(f"{env}: {e}")
                continue
            image_tag = chart_sha(gekozen) if gekozen else None
        if gekozen is None or gekozen not in chart_tags:
            plan.fouten.append(f"{env} volgt {versie}, maar die chart staat niet in Harbor")
            continue
        if image_tag is None or image_tag not in image_tags:
            plan.fouten.append(f"{env} draait chart {gekozen}, maar image {image_tag} staat niet in Harbor")
            continue
        plan.omgevingen[env] = (gekozen, image_tag)
        plan.beschermd.setdefault(gekozen, f"chart van {env}")
        plan.beschermd.setdefault(image_tag, f"image van {env}")

    # 2. De nieuwste builds per soort (op pushtijd) en alles van de laatste uren.
    sha_images = sorted(
        (a for a in images if any(SHA_RE.match(t) for t in a.tags)), key=lambda a: a.push_time, reverse=True
    )
    main_builds = [a for a in sha_images if set(a.tags) & main_shas]
    mr_builds = [a for a in sha_images if not set(a.tags) & main_shas]
    for soort, builds, aantal in (("main", main_builds, behoud_main), ("MR", mr_builds, behoud_mr)):
        for a in builds[:aantal]:
            for t in a.tags:
                plan.beschermd.setdefault(t, f"een van de {aantal} nieuwste {soort}-builds")
    for a in images + charts:
        if a.push_time > grens:
            for t in a.tags:
                plan.beschermd.setdefault(t, f"jonger dan {min_uren} uur")

    if plan.fouten:  # een omgeving niet herleidbaar: niets verwijderen
        return plan

    # 3. Images: alleen sha-tags die nergens beschermd zijn. Releases, latest en onbekende tags blijven.
    weg_shas = set()
    for a in images:
        if not a.tags or not all(SHA_RE.match(t) for t in a.tags):
            continue
        if any(t in plan.beschermd for t in a.tags):
            continue
        plan.weg_images.append(a)
        weg_shas.update(a.tags)

    # 4. Charts: een main- of MR-chart gaat mee met zijn image, of als het image al weg is en de chart oud.
    for a in charts:
        if not a.tags or any(t in plan.beschermd for t in a.tags):
            continue
        shas = [chart_sha(t) for t in a.tags]
        if None in shas:
            continue  # release of onbekend patroon
        if all(s in weg_shas or s not in image_tags for s in shas):
            plan.weg_charts.append(a)

    # Vangnet: nooit een release, latest of iets beschermds in de lijst.
    for a in plan.weg_images + plan.weg_charts:
        for t in a.tags:
            if RELEASE_RE.match(t) or t == "latest" or t in plan.beschermd:
                raise AssertionError(f"plan wil beschermde tag {t} verwijderen")
    return plan


# --- Harbor via harbor-cli ---------------------------------------------------------------------------------------


def harbor(*args: str) -> str:
    uit = subprocess.run(["harbor", *args, "-o", "json"], capture_output=True, text=True, timeout=300)
    if uit.returncode != 0:
        raise SystemExit(f"harbor {' '.join(args)} faalde: {uit.stderr.strip()[-500:]}\nIngelogd? Zie Agents.md.")
    return uit.stdout


def tijd(s: str) -> datetime:
    return datetime.fromisoformat(s)


def artifacts(repo: str) -> list[Artifact]:
    gevonden, pagina = [], 1
    while True:
        payload = json.loads(harbor("artifact", "list", repo, "-n", "100", "-p", str(pagina))).get("Payload") or []
        gevonden += [
            Artifact(a["digest"], tuple(t["name"] for t in a.get("tags") or []), tijd(a["push_time"]), a["size"])
            for a in payload
        ]
        if len(payload) < 100:
            return gevonden
        pagina += 1


def quotum() -> tuple[int, int]:
    q = json.loads(harbor("project", "summary", PROJECT))["summary"]["quota"]
    return q["used"]["storage"], q["hard"]["storage"]


def immutability_problemen(regels: list[dict]) -> list[str]:
    """De release-regel moet er zijn, en geen regel mag builds immutable maken (dan valt er niets op te ruimen)."""
    actief = [r for r in regels if not r.get("disabled")]
    patronen = [
        sel.get("pattern", "")
        for r in actief
        for sel in r.get("tag_selectors", [])
        if sel.get("decoration") == "matches"
    ]
    problemen = []
    if IMMUTABLE_PATROON not in patronen:
        problemen.append(f"geen immutability-regel op release-tags met patroon {IMMUTABLE_PATROON} (Agents.md)")
    problemen += [f"immutability-patroon {p!r} maakt ook builds immutable: haal de * weg" for p in patronen if "*" in p]
    return problemen


def immutability_regels() -> list[dict]:
    regels = json.loads(harbor("tag", "immutable", "list", PROJECT) or "[]") or []
    return regels.get("Payload") or [] if isinstance(regels, dict) else regels


def gib(n: int) -> str:
    return f"{n / 2**30:.1f} GiB"


def toon_plan(plan: Plan, images: list[Artifact], charts: list[Artifact]) -> None:
    print(f"images: {len(images)}, charts: {len(charts)}")
    print("Omgevingen:")
    for env, (chart, image) in sorted(plan.omgevingen.items()):
        print(f"  {env:12} chart {chart}  image {image}")
    for f in plan.fouten:
        print(f"FOUT: {f}", file=sys.stderr)
    if plan.fouten:
        print("Niets verwijderd: eerst de fout oplossen.", file=sys.stderr)
        return
    print(
        f"Op te ruimen: {len(plan.weg_images)} images (max. {gib(sum(a.size for a in plan.weg_images))}, "
        f"gedeelde lagen tellen één keer), {len(plan.weg_charts)} charts"
    )
    for a in sorted(plan.weg_images, key=lambda a: a.push_time):
        print(f"  image {a.push_time:%Y-%m-%d %H:%M} {','.join(a.tags)}")
    print(f"Blijft: {len(images) - len(plan.weg_images)} images, {len(charts) - len(plan.weg_charts)} charts")


def cmd_opruimen(args: argparse.Namespace) -> int:
    images, charts = artifacts(IMAGE_REPO), artifacts(CHART_REPO)
    plan = maak_plan(images, charts, lees_pins(), datetime.now(UTC), args.behoud_main, args.behoud_mr, args.min_uren)
    toon_plan(plan, images, charts)
    if plan.fouten:
        return 1
    if not args.uitvoeren:
        print("Dry-run: niets verwijderd. Met --uitvoeren gaat het echt.")
        return 0
    for repo, lijst in ((IMAGE_REPO, plan.weg_images), (CHART_REPO, plan.weg_charts)):
        for a in lijst:
            harbor("artifact", "delete", f"{repo}@{a.digest}")
    gebruikt, max_ = quotum()
    print(f"Verwijderd. Quotum nu {gib(gebruikt)} van {gib(max_)}.")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    images, charts = artifacts(IMAGE_REPO), artifacts(CHART_REPO)
    plan = maak_plan(images, charts, lees_pins(), datetime.now(UTC))
    gebruikt, max_ = quotum()
    problemen = list(plan.fouten)
    print(f"Quotum: {gib(gebruikt)} van {gib(max_)} ({gebruikt / max_:.0%})")
    if gebruikt / max_ > QUOTUM_DREMPEL:
        problemen.append(f"quotum boven {QUOTUM_DREMPEL:.0%}: draai `opruimen`")
    problemen += immutability_problemen(immutability_regels())
    toon_plan(plan, images, charts)
    for p in problemen:
        if p not in plan.fouten:
            print(f"PROBLEEM: {p}", file=sys.stderr)
    return 1 if problemen else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    p = sub.add_parser("opruimen")
    p.add_argument("--uitvoeren", action="store_true", help="echt verwijderen (standaard dry-run)")
    p.add_argument("--behoud-main", type=int, default=BEHOUD_MAIN)
    p.add_argument("--behoud-mr", type=int, default=BEHOUD_MR)
    p.add_argument("--min-uren", type=int, default=MIN_UREN)
    p.set_defaults(func=cmd_opruimen)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

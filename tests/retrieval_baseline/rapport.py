"""Rapport en baseline van de retrieval-meting per sector en reeks, met onzekerheid (#359).

Rekent alleen op de uitkomsten van harnas.meet; zoekt zelf niet.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from tests.retrieval_baseline import meting
from tests.retrieval_baseline.harnas import Meting, Uitkomst

SECTOREN = ("mbo", "hbo", "wo")
REEKSEN = ("ontwikkel", "test")
BUITEN_PROFIEL = "buiten_profiel"
CELLEN = (
    *(f"{sector}/{reeks}" for sector in SECTOREN for reeks in REEKSEN),
    *(f"totaal/{reeks}" for reeks in REEKSEN),
    BUITEN_PROFIEL,
)
INDICATIEF_ONDER = 10
OPNIEUW_METEN = "UV_PYTHON=3.14 uv run python scripts/meet_retrieval.py --schrijf-baseline"


@dataclass(frozen=True)
class Cel:
    """De cijfers van één rij: zoekinput, vraag als invoer, onbeantwoordbare en kritieke vragen."""

    naam: str
    n: int
    zoekinput: meting.Samenvatting
    vraag: meting.Samenvatting
    onbeantwoordbaar: tuple[int, int]
    kritiek: tuple[int, int]

    @property
    def indicatief(self) -> bool:
        return self.zoekinput.n < INDICATIEF_ONDER


def groepen(uitkomsten: Sequence[Uitkomst]) -> dict[str, list[Uitkomst]]:
    """De uitkomsten per cel; buiten_profiel telt niet mee in het totaal."""
    per_cel: dict[str, list[Uitkomst]] = {naam: [] for naam in CELLEN}
    for u in uitkomsten:
        sector, reeks = u.vraag["sector"], u.vraag["reeks"]
        if sector == BUITEN_PROFIEL:
            per_cel[BUITEN_PROFIEL].append(u)
            continue
        per_cel[f"{sector}/{reeks}"].append(u)
        per_cel[f"totaal/{reeks}"].append(u)
    return per_cel


def _geslaagd(uitkomsten: Sequence[Uitkomst], geslaagd: Callable[[Uitkomst], bool]) -> tuple[int, int]:
    return sum(1 for u in uitkomsten if geslaagd(u)), len(uitkomsten)


def cel(naam: str, uitkomsten: Sequence[Uitkomst]) -> Cel:
    beantwoordbaar = [u for u in uitkomsten if u.vraag["beantwoordbaar"]]
    return Cel(
        naam=naam,
        n=len(uitkomsten),
        zoekinput=meting.samenvatten([u.eerste for u in beantwoordbaar]),
        vraag=meting.samenvatten([u.eerste_vraag for u in beantwoordbaar]),
        onbeantwoordbaar=_geslaagd(
            [u for u in uitkomsten if not u.vraag["beantwoordbaar"]], lambda u: u.geen_kandidaat
        ),
        kritiek=_geslaagd([u for u in uitkomsten if u.vraag["kritiek"]], lambda u: not u.verboden_top),
    )


def cellen(uitkomsten: Sequence[Uitkomst]) -> list[Cel]:
    return [cel(naam, groep) for naam, groep in groepen(uitkomsten).items()]


def _afgerond(waarde: float | None) -> float | None:
    return None if waarde is None else round(waarde, 4)


def _cijfers(c: Cel) -> dict:
    return {
        "n": c.n,
        "n_beantwoordbaar": c.zoekinput.n,
        "recall_at_5": _afgerond(c.zoekinput.recall),
        "recall_at_5_95": [_afgerond(x) for x in c.zoekinput.recall_interval],
        "mrr": _afgerond(c.zoekinput.mrr),
        "mrr_95": [_afgerond(x) for x in c.zoekinput.mrr_interval],
        "recall_at_5_vraag": _afgerond(c.vraag.recall),
        "mrr_vraag": _afgerond(c.vraag.mrr),
        "onbeantwoordbaar_geslaagd": list(c.onbeantwoordbaar),
        "kritiek_geslaagd": list(c.kritiek),
    }


def kritiek_falend(gemeten: Meting) -> dict[str, dict[str, int]]:
    """Per kritieke vraag met een verboden dataset in de top 5: die datasets en hun rang."""
    return {u.vraag["id"]: u.verboden_top for u in gemeten.uitkomsten if u.vraag["kritiek"] and u.verboden_top}


def baseline(gemeten: Meting, snapshot: dict, datum: str) -> dict:
    """De inhoud van baseline.json: catalogussnapshot, meetdatum, metingen per cel en kritiek_falend."""
    return {
        **snapshot,
        "gemeten_op": datum,
        "metingen": {c.naam: _cijfers(c) for c in cellen(gemeten.uitkomsten)},
        "kritiek_falend": kritiek_falend(gemeten),
    }


def nieuw_falend(oud: dict | None, nieuw: dict) -> list[str]:
    """Kritieke vragen die in de nieuwe baseline falen en in de oude niet (release-eis 5)."""
    eerder = set((oud or {}).get("kritiek_falend", {}))
    return sorted(set(nieuw["kritiek_falend"]) - eerder) if oud else []


def _getal(waarde: float | None) -> str:
    return "-" if waarde is None else f"{waarde:.2f}"


def _met_interval(waarde: float | None, interval: tuple[float, float]) -> str:
    return f"{_getal(waarde)} [{interval[0]:.2f}-{interval[1]:.2f}]"


def _verschil(nu: float | None, oud: dict | None, naam: str, sleutel: str) -> str:
    vorig = ((oud or {}).get("metingen", {}).get(naam) or {}).get(sleutel)
    if nu is None or vorig is None:
        return ""
    # Vergelijk zoals baseline.json afrondt; `or 0.0` maakt van -0.0 een gewone 0.
    return f"{round(round(nu, 4) - vorig, 2) or 0.0:+.2f}"


def _breuk(geslaagd: tuple[int, int]) -> str:
    return f"{geslaagd[0]}/{geslaagd[1]}" if geslaagd[1] else "-"


_KOP = (
    f"{'cel':<16}{'n':>4}{'nb':>4}  {'recall@5 [95%]':<19}{'Δ':>6}  {'MRR [95%]':<19}{'Δ':>6}"
    f"  {'vraag r@5':>9}{'vraag MRR':>10}  {'onbeantw.':>9}{'kritiek':>8}"
)


def _rij(c: Cel, oud: dict | None) -> str:
    z = c.zoekinput
    return (
        f"{c.naam:<16}{c.n:>4}{z.n:>4}  {_met_interval(z.recall, z.recall_interval):<19}"
        f"{_verschil(z.recall, oud, c.naam, 'recall_at_5'):>6}  {_met_interval(z.mrr, z.mrr_interval):<19}"
        f"{_verschil(z.mrr, oud, c.naam, 'mrr'):>6}  {_getal(c.vraag.recall):>9}{_getal(c.vraag.mrr):>10}"
        f"  {_breuk(c.onbeantwoordbaar):>9}{_breuk(c.kritiek):>8}"
        f"{'  indicatief' if c.indicatief else ''}"
    ).rstrip()


def _latentie(gemeten: Meting) -> str:
    duren = sorted(u.latentie_ms for u in gemeten.uitkomsten)
    if not duren:
        return "Latentie: geen zoekopdrachten."
    p50, p95 = meting.kwantiel(duren, 0.5), meting.kwantiel(duren, 0.95)
    return f"Latentie per zoekopdracht (zoekinput, deze machine): p50 {p50:.0f} ms, p95 {p95:.0f} ms."


def _kop(gemeten: Meting, oud: dict | None, snapshot: dict) -> list[str]:
    regels = [
        f"Retrieval-baseline search_catalog (#359): {len(gemeten.uitkomsten)} vragen, catalogus "
        f"{snapshot['catalogus_digest']}, top {meting.TOP_N}, zonder LLM en zonder netwerk.",
        "recall@5: aandeel beantwoordbare vragen (nb) met een geaccepteerde dataset in de top 5; Wilson-95%. "
        "MRR: bootstrap-95%. Δ: verschil met baseline.json.",
        f"Indicatief: minder dan {INDICATIEF_ONDER} beantwoordbare vragen; de intervallen zijn breed, lees ze mee.",
    ]
    if oud is None:
        regels.append(f"Geen baseline.json: geen Δ. Leg de meting vast met: {OPNIEUW_METEN}")
    elif oud.get("catalogus_digest") != snapshot["catalogus_digest"]:
        regels.append(
            f"Let op: de catalogus wijkt af van baseline.json ({oud.get('catalogus_digest')}, "
            f"{oud.get('gemeten_op')}); Δ komt dan niet alleen van de zoekcode."
        )
    return regels


def _kritiek_regels(gemeten: Meting, oud: dict | None, toon_test: bool) -> list[str]:
    bekend = set((oud or {}).get("kritiek_falend", {}))
    falend = kritiek_falend(gemeten)
    zichtbaar = {i: v for i, v in falend.items() if toon_test or gemeten.uitkomst(i).vraag["reeks"] != "test"}
    regels = [
        f"Kritiek falend: {vraag_id} ({_rangen(verboden)}){'' if vraag_id in bekend else ' NIEUW'}"
        for vraag_id, verboden in zichtbaar.items()
    ]
    if verborgen := len(falend) - len(zichtbaar):
        regels.append(f"Kritiek falend in de testreeks: {verborgen} (details met --toon-test).")
    return regels


def _rangen(per_id: Mapping[str, int | None]) -> str:
    return ", ".join(f"{i}={'-' if r is None else r}" for i, r in per_id.items())


def _detail(u: Uitkomst) -> str:
    v = u.vraag
    if v["beantwoordbaar"]:
        uitkomst = f"rang {u.eerste or '-'} (vraag {u.eerste_vraag or '-'}); {_rangen(u.rangen)}"
    else:
        uitkomst = "onbeantwoordbaar: " + ("geen kandidaat" if u.geen_kandidaat else "wel kandidaten")
    verboden = f"; verboden in top 5: {_rangen(u.verboden_top)}" if u.verboden_top else ""
    top = ", ".join(u.ranking[: meting.K]) or "-"
    return f"  {v['id']:<7} {uitkomst}{verboden} | top 5: {top}"


def _details(gemeten: Meting, toon_test: bool) -> list[str]:
    reeksen = REEKSEN if toon_test else ("ontwikkel",)
    regels: list[str] = []
    for reeks in reeksen:
        regels += ["", f"Details {reeks} ({meting.TOP_N} treffers; rang - is niet gevonden):"]
        regels += [_detail(u) for u in gemeten.uitkomsten if u.vraag["reeks"] == reeks]
    if not toon_test:
        regels += ["", "Details test verborgen: de testreeks is ongezien; --toon-test toont ze."]
    return regels


def tekst(gemeten: Meting, oud: dict | None, snapshot: dict, toon_test: bool = False) -> str:
    """Het rapport: kop, tabel per cel, latentie, kritieke missers en details per vraag."""
    regels = [*_kop(gemeten, oud, snapshot), "", _KOP]
    regels += [_rij(c, oud) for c in cellen(gemeten.uitkomsten)]
    regels += ["", _latentie(gemeten), f"Netwerkpogingen: {len(gemeten.netwerkpogingen)}."]
    regels += _kritiek_regels(gemeten, oud, toon_test)
    regels += _details(gemeten, toon_test)
    return "\n".join(regels)

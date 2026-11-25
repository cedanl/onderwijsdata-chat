"""De wekelijkse kwaliteitsaudit (#1250): scripts/kwaliteitsaudit.py maakt uit een logexport of de Prometheus-tellers
een weekrapport in Markdown, zonder vraag- of antwoordtekst, en opent zelf nooit een MR.
"""

import ast
import json
import re
from datetime import date
from pathlib import Path

import pytest

from core import metrics
from scripts import kwaliteitsaudit

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "kwaliteitsaudit"
LOG = FIXTURES / "logexport.jsonl"
DEZE = FIXTURES / "prometheus-deze-week.json"
VORIGE = FIXTURES / "prometheus-vorige-week.json"
TOT = date(2026, 11, 30)
VRAAGTEKST = "geheimvak"


def _rij(rapport: str, begin: str) -> str:
    [rij] = [r for r in rapport.splitlines() if r.startswith(begin)]
    return rij


def _sectie(rapport: str, kop: str) -> str:
    return rapport.split(f"## {kop}\n", 1)[1].split("\n## ", 1)[0]


@pytest.fixture(scope="module")
def uit_log() -> str:
    deze, vorige, gelezen = kwaliteitsaudit.lees_log(LOG, TOT)
    return kwaliteitsaudit.rapport(deze, vorige, TOT, bron=f"logexport `{LOG.name}`", gelezen=gelezen)


@pytest.fixture(scope="module")
def uit_prometheus() -> str:
    deze = kwaliteitsaudit.lees_prometheus(DEZE)
    vorige = kwaliteitsaudit.lees_prometheus(VORIGE)
    return kwaliteitsaudit.rapport(deze, vorige, TOT, bron="Prometheus")


def test_de_logexport_telt_per_controle_en_tool_met_de_trend_tegen_de_vorige_week(uit_log):
    assert uit_log.startswith("# Kwaliteitsaudit 2026-11-23 t/m 2026-11-29\n")
    assert "vorige week: 2026-11-16 t/m 2026-11-22" in uit_log
    samenvatting = _sectie(uit_log, "Samenvatting")
    assert _rij(samenvatting, "| Antwoorden gecontroleerd") == "| Antwoorden gecontroleerd | 3 | 1 | +2 |"
    assert _rij(samenvatting, "| Herkansingen") == "| Herkansingen | 1 | 1 | 0 |"
    assert _rij(samenvatting, "| Ingehouden antwoorden") == "| Ingehouden antwoorden | 1 | 0 | nieuw |"
    assert _rij(samenvatting, "| Stappenbudget op") == "| Stappenbudget op | 1 | 0 | nieuw |"
    assert _rij(samenvatting, "| Toolweigeringen") == "| Toolweigeringen | 5 | 1 | +4 |"

    controles = _sectie(uit_log, "Per controle")
    # Controle | hard | zacht | niet gecontroleerd | ok | misgegaan | vorige week | trend
    assert _rij(controles, "| ongedekte_getallen") == "| ongedekte_getallen | 2 | 0 | 0 | 1 | 2 | 1 | +1 |"
    assert _rij(controles, "| metatekst") == "| metatekst | 0 | 1 | 0 | 1 | 1 | 0 | nieuw |"
    assert _rij(controles, "| verkeerde_antwoordtaal") == "| verkeerde_antwoordtaal | 0 | 0 | 1 | 1 | 1 | 0 | nieuw |"
    assert _rij(controles, "| overig") == "| overig | 1 | 0 | 0 | 0 | 1 | 0 | nieuw |"

    tools = _sectie(uit_log, "Per tool")
    # Tool | op slot | limiet | afgekapt | totaal | vorige week | trend
    assert _rij(tools, "| search_catalog") == "| search_catalog | 0 | 2 | 0 | 2 | 1 | +1 |"
    assert _rij(tools, "| get_cbs_data") == "| get_cbs_data | 1 | 0 | 0 | 1 | 0 | nieuw |"
    assert _rij(tools, "| query_data") == "| query_data | 0 | 0 | 1 | 1 | 0 | nieuw |"
    assert _rij(tools, "| overig") == "| overig | 1 | 0 | 0 | 1 | 0 | nieuw |"


def test_de_top_10_van_wat_het_vaakst_misgaat(uit_log):
    top = [r for r in _sectie(uit_log, "Top 10: wat het vaakst misgaat").splitlines() if re.match(r"^\| \d+ \|", r)]
    assert len(top) == 10
    assert top[0] == "| 1 | controle ongedekte_getallen: hard | 2 | 1 | +1 |"
    assert top[1] == "| 2 | tool search_catalog: limiet | 2 | 1 | +1 |"
    assert [r.split("|")[2].strip() for r in top[2:]] == [
        "controle metatekst: zacht",
        "controle overig: hard",
        "controle verkeerde_antwoordtaal: niet gecontroleerd",
        "ingehouden antwoorden",
        "stappenbudget op",
        "tool get_cbs_data: op slot",
        "tool overig: op slot",
        "tool query_data: afgekapt",
    ]


def test_de_tellers_uit_prometheus_geven_hetzelfde_rapport(uit_prometheus):
    assert "Bron: Prometheus" in uit_prometheus
    samenvatting = _sectie(uit_prometheus, "Samenvatting")
    assert _rij(samenvatting, "| Antwoorden gecontroleerd") == "| Antwoorden gecontroleerd | 242 | 208 | +34 |"
    assert _rij(samenvatting, "| Herkansingen") == "| Herkansingen | 9 | 11 | -2 |"
    assert _rij(samenvatting, "| Ingehouden antwoorden") == "| Ingehouden antwoorden | 2 | 0 | nieuw |"
    assert _rij(samenvatting, "| Stappenbudget op") == "| Stappenbudget op | 1 | 1 | 0 |"
    controles = _sectie(uit_prometheus, "Per controle")
    # increase() geeft kommagetallen: afgerond op hele aantallen.
    assert _rij(controles, "| ongedekte_getallen") == "| ongedekte_getallen | 12 | 0 | 0 | 230 | 12 | 8 | +4 |"
    # Een label buiten de vaste lijst (hier tekst) telt als overig, ook als het uit Prometheus komt.
    assert _rij(controles, "| overig") == "| overig | 1 | 0 | 0 | 0 | 1 | 0 | nieuw |"
    tools = _sectie(uit_prometheus, "Per tool")
    assert _rij(tools, "| query_data") == "| query_data | 0 | 0 | 7 | 7 | 7 | 0 |"
    top = _sectie(uit_prometheus, "Top 10: wat het vaakst misgaat")
    assert "| 1 | controle ongedekte_getallen: hard | 12 | 8 | +4 |" in top


def test_een_duidelijk_patroon_wordt_een_kandidaat_voor_een_mr_met_review(uit_prometheus, uit_log):
    kandidaten = _sectie(uit_prometheus, "Kandidaat-wijzigingen")
    [regel] = [r for r in kandidaten.splitlines() if r.startswith("- ")]
    assert regel.startswith("- controle ongedekte_getallen: hard (12, vorige week 8):")
    assert "domeinregel" in regel
    assert "MR" in kandidaten and "review" in kandidaten and "nooit automatisch gemerged" in kandidaten
    # Te weinig om een patroon te zijn: geen kandidaat, wel de uitleg.
    assert not [r for r in _sectie(uit_log, "Kandidaat-wijzigingen").splitlines() if r.startswith("- ")]


def test_geen_vraag_of_antwoordtekst_uit_het_log_in_het_rapport(uit_log):
    # De logexport heeft de vraag in TOOL CALL (DEBUG), TOOL RESULT (INFO), CONTROLE MELDINGEN, een traceback, een
    # controlenaam en een toolnaam; het script leest alleen de vaste regelsoorten en de namen uit de vaste lijsten.
    assert VRAAGTEKST in LOG.read_text(encoding="utf-8")
    assert VRAAGTEKST not in uit_log
    for woord in ("6.340", "HU?", "openai/gpt-4o", "abcd1234", "c-2", "0f0f0f0f"):
        assert woord not in uit_log, woord
    assert set(kwaliteitsaudit.REGELSOORTEN) == {
        "CONTROLES",
        "HERKANSING",
        "ANTWOORD INGEHOUDEN",
        "STAPPENBUDGET OP",
        "TOOL OP SLOT",
        "TOOL LIMIET",
        "TOOL_AFGEKAPT",
    }


def test_alleen_de_vaste_regelsoorten_tellen(tmp_path):
    log = tmp_path / "log.jsonl"
    regels = [
        {"timestamp": "2026-11-24T10:00:00+00:00", "level": "DEBUG", "message": "CONTROLES  metatekst=hard"},
        {"timestamp": "2026-11-24T10:00:00+00:00", "level": "INFO", "message": "TOOL CALL get_maat {}"},
        {"timestamp": "2026-11-24T10:00:00+00:00", "level": "INFO", "message": "xCONTROLES  metatekst=hard"},
        {"timestamp": "2026-11-24T10:00:00+00:00", "level": "INFO", "message": "CONTROLES  metatekst=hard"},
    ]
    log.write_text("\n".join(json.dumps(r) for r in regels), encoding="utf-8")
    deze, _, gelezen = kwaliteitsaudit.lees_log(log, TOT)
    assert gelezen == (4, 1)
    assert deze.controles == {("metatekst", "hard"): 1}


def test_de_vaste_lijsten_zijn_die_van_de_tellers():
    assert kwaliteitsaudit.controlenamen() == metrics.controlenamen()
    assert kwaliteitsaudit.toolnamen() == metrics.toolnamen()
    assert kwaliteitsaudit.CONTROLE_UITKOMSTEN == metrics.CONTROLE_UITKOMSTEN
    assert kwaliteitsaudit.TOOL_WEIGERREDENEN == metrics.TOOL_WEIGERREDENEN


def test_het_script_opent_pusht_of_merget_niets_en_roept_geen_model_aan():
    bron = (ROOT / "scripts" / "kwaliteitsaudit.py").read_text(encoding="utf-8")
    boom = ast.parse(bron)
    modules = {a.name.split(".")[0] for n in ast.walk(boom) if isinstance(n, ast.Import) for a in n.names}
    modules |= {n.module.split(".")[0] for n in ast.walk(boom) if isinstance(n, ast.ImportFrom) and n.module}
    # Alleen de standaardbibliotheek voor lezen, rekenen en schrijven: geen proces, netwerk, git, forge of model.
    assert modules <= {
        "__future__",
        "argparse",
        "ast",
        "collections",
        "dataclasses",
        "datetime",
        "json",
        "pathlib",
        "re",
        "sys",
    }
    aanroepen = {
        n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
        for n in ast.walk(boom)
        if isinstance(n, ast.Call)
    }
    assert not aanroepen & {
        "system",
        "popen",
        "run",
        "urlopen",
        "completion",
        "acompletion",
        "exec",
        "eval",
        "__import__",
    }
    teksten = " ".join(n.value for n in ast.walk(boom) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    for woord in ("glab", "git push", "git ", "merge_request", "gh pr", "api/v4", "http://", "https://"):
        assert woord not in teksten.replace("geen MR", ""), woord


def test_het_script_schrijft_het_rapport(tmp_path, capsys):
    uit = tmp_path / "rapport.md"
    assert kwaliteitsaudit.main(["--log", str(LOG), "--tot", "2026-11-30", "--uit", str(uit)]) == 0
    assert uit.read_text(encoding="utf-8").startswith("# Kwaliteitsaudit 2026-11-23 t/m 2026-11-29")
    assert (
        kwaliteitsaudit.main(["--prometheus", str(DEZE), "--prometheus-vorige", str(VORIGE), "--tot", "2026-11-30"])
        == 0
    )
    assert "| ongedekte_getallen | 12 |" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        kwaliteitsaudit.main(["--log", str(LOG), "--prometheus", str(DEZE)])
    with pytest.raises(SystemExit):
        kwaliteitsaudit.main(["--prometheus", str(DEZE)])

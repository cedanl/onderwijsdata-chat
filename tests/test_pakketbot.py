"""De bot van de geplande pakketjobs (#887): MR met auto-merge in plaats van een push op main, één issue per controle."""

import argparse
import json
import subprocess
from pathlib import Path

import httpx
import pytest

from scripts import pakketbot

ENV = {
    "PAKKETBOT_TOKEN": "geheim-token",
    "CI_API_V4_URL": "https://gitlab.test/api/v4",
    "CI_PROJECT_ID": "42",
    "CI_JOB_NAME": "cbs:discovery",
    "CI_PIPELINE_URL": "https://gitlab.test/p/1",
    "CI_DEFAULT_BRANCH": "main",
}


class NepGitLab:
    """Een minimale GitLab-API in het geheugen: issues, notes en MR's, met een log van elke schrijfactie."""

    def __init__(self, issues=None, mrs=None, mr_reeks=None, merge_status=405):
        self.issues = issues or []
        self.mrs = mrs or []
        self.mr_reeks = list(mr_reeks or [])  # opeenvolgende antwoorden op GET merge_requests/<iid>
        self.merge_status = merge_status
        self.schrijf = []
        self.headers = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.headers.append(dict(request.headers))
        pad = request.url.path.removeprefix("/api/v4/projects/42/")
        if request.method != "GET":
            json_body = "json" in request.headers.get("content-type", "")
            body = json.loads(request.content) if json_body else request.content.decode()
            self.schrijf.append((request.method, pad, body))
        if pad == "":
            return httpx.Response(200, json={"path_with_namespace": "groep/onderwijsdata-chat"})
        if pad == "issues" and request.method == "GET":
            return httpx.Response(200, json=self.issues)
        if pad == "issues" and request.method == "POST":
            return httpx.Response(201, json={"iid": 900, "web_url": "https://gitlab.test/i/900"})
        if pad.startswith("issues/"):
            return httpx.Response(200, json={})
        if pad == "merge_requests" and request.method == "GET":
            return httpx.Response(200, json=self.mrs)
        if pad == "merge_requests" and request.method == "POST":
            return httpx.Response(201, json={"iid": 77, "web_url": "https://gitlab.test/mr/77"})
        if pad.endswith("/merge"):
            return httpx.Response(self.merge_status, json={})
        if pad.startswith("merge_requests/") and request.method == "PUT":
            return httpx.Response(200, json={"iid": int(pad.split("/")[1]), "web_url": "https://gitlab.test/mr/x"})
        if pad.startswith("merge_requests/"):
            return httpx.Response(200, json=self.mr_reeks.pop(0) if len(self.mr_reeks) > 1 else self.mr_reeks[0])
        return httpx.Response(404)


def _gl(nep: NepGitLab, env=ENV) -> httpx.Client:
    return pakketbot.gitlab(env, transport=httpx.MockTransport(nep))


# --- token -----------------------------------------------------------------------------------


def test_zonder_token_faalt_de_job_met_een_melding_die_de_variabele_noemt(capsys):
    code = pakketbot.main(["controleer"], env={k: v for k, v in ENV.items() if k != "PAKKETBOT_TOKEN"})
    fout = capsys.readouterr().err
    assert code == 2
    assert "PAKKETBOT_TOKEN ontbreekt" in fout and "masked en protected" in fout and "write_repository" in fout


def test_een_leeg_token_telt_als_ontbrekend():
    with pytest.raises(pakketbot.BotFout) as fout:
        pakketbot.token({"PAKKETBOT_TOKEN": "  "})
    assert fout.value.code == 2


def test_het_token_gaat_alleen_als_header_mee_en_komt_niet_in_de_uitvoer(capsys, monkeypatch):
    nep = NepGitLab()
    echte = pakketbot.gitlab
    monkeypatch.setattr(pakketbot, "gitlab", lambda env: echte(env, transport=httpx.MockTransport(nep)))
    assert pakketbot.main(["controleer"], env=ENV) == 0
    uit = capsys.readouterr()
    assert "groep/onderwijsdata-chat" in uit.out
    assert "geheim-token" not in uit.out + uit.err
    assert nep.headers[0]["private-token"] == "geheim-token"


def test_een_geweigerd_token_noemt_rol_en_scopes():
    def weiger(_request):
        return httpx.Response(401, json={"message": "401 Unauthorized"})

    with pytest.raises(pakketbot.BotFout, match="rol en scopes van PAKKETBOT_TOKEN"):
        pakketbot.controleer(pakketbot.gitlab(ENV, transport=httpx.MockTransport(weiger)))


# --- issues met dedup ------------------------------------------------------------------------


def test_een_nieuwe_bevinding_maakt_een_issue():
    nep = NepGitLab()
    uit = pakketbot.issue_bijwerken(_gl(nep), "Titel", "kern", ENV, "2026-11-09")
    assert uit.startswith("nieuw issue #900")
    ((methode, pad, body),) = nep.schrijf
    assert (methode, pad) == ("POST", "issues")
    assert body["title"] == "Titel" and body["description"].startswith("kern\n\n<!-- pakketbot -->")
    assert "cbs:discovery" in body["description"]


def test_dezelfde_stand_raakt_het_open_issue_niet_aan_ook_als_de_pipeline_anders_is():
    bestaand = {
        "iid": 5,
        "title": "Titel",
        "web_url": "u",
        "description": "kern\n\n<!-- pakketbot -->\n_andere pipeline_",
    }
    nep = NepGitLab(issues=[bestaand])
    uit = pakketbot.issue_bijwerken(_gl(nep), "Titel", "kern", ENV, "2026-11-09")
    assert "niets gewijzigd" in uit
    assert nep.schrijf == []


def test_een_andere_stand_vervangt_de_beschrijving_en_zet_een_notitie():
    bestaand = {"iid": 5, "title": "Titel", "web_url": "u", "description": "oude kern\n\n<!-- pakketbot -->"}
    nep = NepGitLab(issues=[bestaand])
    pakketbot.issue_bijwerken(_gl(nep), "Titel", "nieuwe kern", ENV, "2026-11-09")
    assert [(m, p) for m, p, _ in nep.schrijf] == [("PUT", "issues/5"), ("POST", "issues/5/notes")]
    assert nep.schrijf[0][2]["description"].startswith("nieuwe kern")
    assert "2026-11-09" in nep.schrijf[1][2]["body"] and "nieuwe kern" in nep.schrijf[1][2]["body"]


def test_een_issue_met_een_langere_titel_telt_niet_als_hetzelfde():
    nep = NepGitLab(issues=[{"iid": 5, "title": "Titel (oud)", "web_url": "u", "description": "kern"}])
    assert pakketbot.open_issue(_gl(nep), "Titel") is None


def _rapport(n: int) -> dict:
    nieuw = [
        {"dataset_id": f"8{i:04d}NED", "titel": f"Tabel {i}", "classificatie": "ho", "thema": "Onderwijs"}
        for i in range(n)
    ]
    samenvatting = {"nieuw_voor_review": n, "nieuw_voor_review_actief": n, "nieuw_voor_review_historisch": 0}
    return {"samenvatting": samenvatting, "nieuw_voor_review": nieuw}


def test_discovery_zonder_nieuwe_tabellen_meldt_niets():
    assert pakketbot.discovery_tekst(_rapport(0)) is None


def test_discovery_noemt_hoogstens_vijftig_tabellen_met_id_en_classificatie():
    tekst = pakketbot.discovery_tekst(_rapport(60))
    assert tekst is not None
    assert tekst.startswith("60 nieuwe tabel(len)")
    assert "- `80000NED` Tabel 0 (ho; Onderwijs)" in tekst
    assert tekst.count("\n- `") == 50


def _broncontrole(code: int, tmp_path: Path) -> argparse.Namespace:
    pad = tmp_path / "meldingen.txt"
    pad.write_text("DUO: nieuwe dataset in CKAN die niet in de catalogus staat: x\n\n")
    return argparse.Namespace(meldingen=str(pad), code=code)


def test_broncontrole_zonder_meldingen_maakt_geen_issue(tmp_path):
    nep = NepGitLab()
    assert "niets te melden" in pakketbot.cmd_meld_broncontrole(_broncontrole(0, tmp_path), ENV, _gl(nep))
    assert nep.schrijf == []


def test_een_mislukte_broncontrole_is_een_rode_job_en_geen_issue(tmp_path):
    nep = NepGitLab()
    with pytest.raises(pakketbot.BotFout, match="mislukt"):
        pakketbot.cmd_meld_broncontrole(_broncontrole(1, tmp_path), ENV, _gl(nep))
    assert nep.schrijf == []


def test_reviewmeldingen_van_de_broncontrole_komen_als_lijst_in_het_issue(tmp_path):
    nep = NepGitLab()
    pakketbot.cmd_meld_broncontrole(_broncontrole(10, tmp_path), ENV, _gl(nep))
    body = nep.schrijf[0][2]
    assert body["title"] == pakketbot.BRONCONTROLE_TITEL
    assert "- DUO: nieuwe dataset in CKAN die niet in de catalogus staat: x" in body["description"]


# --- MR met auto-merge -----------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Een checkout met een bare remote, zoals de runner hem maakt (detached HEAD op main)."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(remote))
    werk = tmp_path / "werk"
    werk.mkdir()
    _git(werk, "init", "--quiet", "-b", "main")
    (werk / "data").mkdir()
    (werk / "data/a.json").write_text("1")
    (werk / "data/weg.json").write_text("x")
    (werk / "elders.txt").write_text("blijft")
    _git(werk, "add", ".")
    _git(werk, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "start")
    _git(werk, "checkout", "--quiet", "--detach")
    monkeypatch.chdir(werk)
    return werk, remote


def test_alleen_wijzigingen_onder_de_paden_tellen(repo):
    werk, _ = repo
    assert pakketbot.gewijzigde_paden(["data"]) == []
    (werk / "elders.txt").write_text("anders")
    assert pakketbot.gewijzigde_paden(["data"]) == []
    (werk / "data/a.json").write_text("2")
    (werk / "data/nieuw").mkdir()
    (werk / "data/nieuw/b.png").write_bytes(b"png")
    (werk / "data/weg.json").unlink()
    assert pakketbot.gewijzigde_paden(["data"]) == ["data/a.json", "data/nieuw/b.png", "data/weg.json"]


def test_de_commit_bevat_alleen_de_paden_en_gaat_met_force_naar_de_botbranch(repo):
    werk, remote = repo
    (werk / "data/a.json").write_text("2")
    (werk / "data/weg.json").unlink()
    (werk / "elders.txt").write_text("anders")
    sha = pakketbot.commit_en_push("bot/test", "chore: test", ["data"], str(remote), ENV)
    assert _git(remote, "rev-parse", "refs/heads/bot/test").strip() == sha
    assert sorted(_git(remote, "diff", "--name-only", f"{sha}~1", sha).split()) == [
        "data/a.json",
        "data/weg.json",
    ]
    assert "pakketbot" in _git(remote, "log", "-1", "--format=%an", sha)
    # Een tweede run schrijft de branch opnieuw vanaf de basis, ook als die al bestond.
    _git(werk, "checkout", "--quiet", "--detach", "HEAD~1")
    (werk / "data/a.json").write_text("3")
    sha2 = pakketbot.commit_en_push("bot/test", "chore: test", ["data"], str(remote), ENV)
    assert _git(remote, "rev-parse", "refs/heads/bot/test").strip() == sha2


def test_het_token_staat_niet_op_de_opdrachtregel_van_git(repo):
    werk, remote = repo
    (werk / "data/a.json").write_text("2")
    gezien = []

    def run(cmd, **kw):
        gezien.append((cmd, kw.get("env")))
        return subprocess.run(cmd, **kw)

    pakketbot.commit_en_push("bot/test", "chore: test", ["data"], str(remote), ENV, run=run)
    assert all("geheim-token" not in " ".join(cmd) for cmd, _ in gezien)
    push_cmd, push_env = next((c, e) for c, e in gezien if "push" in c)
    assert push_env["PAKKETBOT_TOKEN"] == "geheim-token"
    assert "${PAKKETBOT_TOKEN}" in " ".join(push_cmd)


def test_een_open_mr_van_de_botbranch_wordt_hergebruikt():
    nep = NepGitLab(mrs=[{"iid": 12, "web_url": "u"}])
    mr = pakketbot.mr_openen(_gl(nep), "bot/test", "titel", "tekst", "main")
    assert mr["iid"] == 12
    assert [(m, p) for m, p, _ in nep.schrijf] == [("PUT", "merge_requests/12")]


def test_een_nieuwe_mr_ruimt_de_botbranch_op_na_de_merge():
    nep = NepGitLab()
    pakketbot.mr_openen(_gl(nep), "bot/test", "titel", "tekst", "main")
    ((methode, pad, body),) = nep.schrijf
    assert (methode, pad) == ("POST", "merge_requests")
    assert body["source_branch"] == "bot/test" and body["target_branch"] == "main" and body["remove_source_branch"]


def test_auto_merge_wacht_op_de_lopende_pipeline_van_de_gepushte_commit():
    reeks = [
        {"sha": "oud", "head_pipeline": {"status": "success"}},  # de MR staat nog op de vorige push
        {"sha": "abc", "head_pipeline": None},  # pipeline bestaat nog niet: een PUT gaf hier 405
        {"sha": "abc", "head_pipeline": {"status": "running"}},
        {"sha": "abc", "head_pipeline": {"status": "running"}, "merge_when_pipeline_succeeds": True},
    ]
    nep = NepGitLab(mr_reeks=reeks, merge_status=200)
    gewacht = []
    assert pakketbot.auto_merge(_gl(nep), 77, "abc", wacht=gewacht.append) is True
    puts = [(p, b) for m, p, b in nep.schrijf if m == "PUT"]
    assert len(puts) == 1 and puts[0][0] == "merge_requests/77/merge"
    assert "auto_merge=true" in puts[0][1] and "sha=abc" in puts[0][1]


def test_auto_merge_probeert_opnieuw_na_een_405_en_geeft_op_na_de_pogingen():
    nep = NepGitLab(mr_reeks=[{"sha": "abc", "head_pipeline": {"status": "running"}}], merge_status=405)
    assert pakketbot.auto_merge(_gl(nep), 77, "abc", wacht=lambda s: None, pogingen=3) is False
    assert sum(1 for m, _, _ in nep.schrijf if m == "PUT") == 3


def test_een_rode_mr_pipeline_stopt_het_wachten():
    nep = NepGitLab(mr_reeks=[{"sha": "abc", "head_pipeline": {"status": "failed", "web_url": "p"}}])
    with pytest.raises(pakketbot.BotFout, match="failed"):
        pakketbot.auto_merge(_gl(nep), 77, "abc", wacht=lambda s: None)


def test_zonder_wijzigingen_geen_commit_en_geen_mr(repo):
    nep = NepGitLab()
    args = argparse.Namespace(paden=["data"], branch="bot/test", titel="t", toelichting="")
    assert "Geen wijzigingen" in pakketbot.cmd_mr(args, ENV, _gl(nep))
    assert nep.schrijf == []


def test_de_mr_beschrijving_noemt_de_bestanden_en_de_job():
    tekst = pakketbot.mr_beschrijving(["a.json", "b.json"], "Waarom.", ENV)
    assert tekst.startswith("Waarom.")
    assert "Gewijzigde bestanden (2)" in tekst and "- `a.json`" in tekst and "cbs:discovery" in tekst
    for woord in ("Closes", "Fixes", "Resolves"):
        assert woord not in tekst

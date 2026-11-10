"""Wat elke omgeving uit manifests/ nodig heeft om te draaien zoals test (#421).

Productie stond in geen audit; daar ontbrak de middleware waar de ingress naar
verwijst, en draaiden drie pods met staat in het geheugen.
"""

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_CHART = yaml.safe_load((_ROOT / "charts/onderwijsdata-chat/values.yaml").read_text())
_OMGEVINGEN = sorted(p.parent for p in _ROOT.glob("manifests/*/values.yaml"))
_MIDDLEWARE = "traefik.ingress.kubernetes.io/router.middlewares"


def _values(omgeving: Path) -> dict:
    return yaml.safe_load((omgeving / "values.yaml").read_text())


@pytest.mark.parametrize("omgeving", _OMGEVINGEN, ids=lambda p: p.name)
def test_middleware_van_de_ingress_wordt_meegeleverd(omgeving):
    # Helm voegt de annotaties van chart en omgeving samen; null haalt er een weg.
    annotaties = {
        **_CHART["ingress"]["web"]["annotations"],
        **(_values(omgeving)["ingress"]["web"].get("annotations") or {}),
    }
    resources = yaml.safe_load((omgeving / "kustomization.yaml").read_text())["resources"]
    if annotaties.get(_MIDDLEWARE):
        assert "middleware.yaml" in resources


@pytest.mark.parametrize("omgeving", _OMGEVINGEN, ids=lambda p: p.name)
def test_een_pod_zolang_de_staat_in_het_geheugen_leeft(omgeving):
    # tools/store.py en de rate limiters zijn per pod: een tweede pod kent de tabel
    # achter een CSV-download niet. Eén pod is het besluit voor de eerste productie (ADR-011, #677); opschalen is #984.
    values = _values(omgeving)
    assert values.get("replicaCount", _CHART["replicaCount"]) == 1
    # Geen HPA-knop: de chart had `autoscaling.enabled` zonder HPA-template; aan liet hij alleen `replicas` weg.
    assert "autoscaling" not in values
    assert "autoscaling" not in _CHART


# ── Opschoning na de bewaartermijn (#485): CronJob in de chart, per omgeving aan of uit ──

# De opschoning draait op test, playground en de OTC-omgevingen (#674): de bewaartermijn van docs/privacy.md geldt
# daar ook. Development en de vervallen map production doen niet mee.
_OPSCHONEN_AAN = {"test", "playground", "staging-otc", "production-otc"}
_QUOTUM_CPU_MILLI = 1000  # ResourceQuota limits.cpu van de namespace op test en playground


def _milli(cpu: str) -> int:
    return int(cpu[:-1]) if cpu.endswith("m") else int(float(cpu) * 1000)


def test_de_chart_schoont_standaard_niet_op():
    assert _CHART["opschonen"]["enabled"] is False
    assert _CHART["opschonen"]["droog"] is False


@pytest.mark.parametrize("omgeving", _OMGEVINGEN, ids=lambda p: p.name)
def test_opschonen_alleen_op_de_omgevingen_met_een_bewaartermijn(omgeving):
    aan = (_values(omgeving).get("opschonen") or {}).get("enabled", _CHART["opschonen"]["enabled"])
    assert aan is (omgeving.name in _OPSCHONEN_AAN)


@pytest.mark.parametrize("omgeving", sorted(_OPSCHONEN_AAN))
def test_opschonen_past_in_het_quotum_en_heeft_postgres(omgeving):
    """De CronJob-pod draait naast de app; samen mogen ze niet boven limits.cpu uit, anders start hij nooit."""
    values = _values(_ROOT / "manifests" / omgeving)
    app = _milli(values["resources"]["limits"]["cpu"])
    opschonen = _milli(_CHART["opschonen"]["resources"]["limits"]["cpu"])
    assert app + opschonen <= _QUOTUM_CPU_MILLI
    assert "POSTGRES_URI" in {e["name"] for e in values["env"]}


def _helm(*args: str) -> str:
    import os
    import shutil
    import subprocess

    if not shutil.which("helm"):
        # Lokaal een skip; in CI zou een image zonder helm de chart-tests stil overslaan (#768).
        if os.environ.get("CI"):
            pytest.fail("helm ontbreekt in CI: de chart-tests (#675) mogen daar niet worden overgeslagen")
        pytest.skip("helm niet geïnstalleerd")
    return subprocess.run(["helm", *args], capture_output=True, text=True, check=True).stdout


def test_cronjob_draait_de_opschoning_zonder_andere_geheimen_en_buiten_de_service():
    documenten = [
        d
        for d in yaml.safe_load_all(
            _helm(
                "template",
                "onderwijsdata-chat",
                str(_ROOT / "charts/onderwijsdata-chat"),
                "-f",
                str(_ROOT / "manifests/base/values-base.yaml"),
                "-f",
                str(_ROOT / "manifests/test/values.yaml"),
            )
        )
        if d
    ]
    cronjob = next(d for d in documenten if d["kind"] == "CronJob")
    service = next(d for d in documenten if d["kind"] == "Service")
    pod = cronjob["spec"]["jobTemplate"]["spec"]["template"]
    container = pod["spec"]["containers"][0]
    assert container["command"][-2:] == ["-m", "persistence.opschonen"]
    assert "args" not in container  # niet droog: echt opschonen
    assert [e["name"] for e in container["env"]] == ["POSTGRES_URI"]
    assert pod["spec"]["automountServiceAccountToken"] is False
    selector = service["spec"]["selector"]
    assert any(pod["metadata"]["labels"].get(k) != v for k, v in selector.items())
    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"


def test_cronjob_weigert_zonder_postgres():
    import subprocess

    with pytest.raises(subprocess.CalledProcessError) as fout:
        _helm("template", "x", str(_ROOT / "charts/onderwijsdata-chat"), "--set", "opschonen.enabled=true")
    assert "POSTGRES_URI" in fout.value.stderr


# ── Chart-hardening (#675) ──


def _gerenderd(omgeving: str) -> list[dict]:
    uitvoer = _helm(
        "template",
        "onderwijsdata-chat",
        str(_ROOT / "charts/onderwijsdata-chat"),
        "-f",
        str(_ROOT / "manifests/base/values-base.yaml"),
        "-f",
        str(_ROOT / f"manifests/{omgeving}/values.yaml"),
    )
    return [d for d in yaml.safe_load_all(uitvoer) if d]


def _pods(documenten: list[dict]) -> list[dict]:
    deployment = next(d for d in documenten if d["kind"] == "Deployment")
    cronjob = next(d for d in documenten if d["kind"] == "CronJob")
    return [deployment["spec"]["template"]["spec"], cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]]


@pytest.mark.parametrize("omgeving", ["test", "playground"])
def test_readiness_kijkt_naar_de_database_en_liveness_is_geduldig(omgeving):
    pod = _pods(_gerenderd(omgeving))[0]
    container = pod["containers"][0]
    assert container["readinessProbe"]["httpGet"]["path"] == "/ready"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["livenessProbe"]["timeoutSeconds"] >= 5
    assert container["startupProbe"]["httpGet"]["path"] == "/health"
    assert pod["terminationGracePeriodSeconds"] > 45  # ruimer dan --timeout-graceful-shutdown


@pytest.mark.parametrize("omgeving", ["test", "playground"])
def test_alleen_tmp_is_beschrijfbaar(omgeving):
    for pod in _pods(_gerenderd(omgeving)):
        container = pod["containers"][0]
        assert container["securityContext"]["readOnlyRootFilesystem"] is True
        assert {"name": "tmp", "mountPath": "/tmp"} in container["volumeMounts"]
        assert any(v["name"] == "tmp" and "emptyDir" in v for v in pod["volumes"])


def test_geen_serviceaccount_token_en_geen_nepsleutels_in_de_chart():
    documenten = _gerenderd("test")
    account = next(d for d in documenten if d["kind"] == "ServiceAccount")
    assert account["automountServiceAccountToken"] is False
    assert not [e for e in _CHART["env"] if e["name"].endswith("_API_KEY")]


def _uvicorn_termijn() -> int:
    cmd = (_ROOT / "Dockerfile").read_text().split("CMD ")[-1]
    argumenten = yaml.safe_load(cmd)
    return int(argumenten[argumenten.index("--timeout-graceful-shutdown") + 1])


def test_uvicorn_stopt_binnen_de_termijn_van_kubernetes():
    assert _uvicorn_termijn() < _CHART["terminationGracePeriodSeconds"]


@pytest.mark.parametrize("omgeving", [p.name for p in _OMGEVINGEN])
def test_elke_omgeving_rendert_een_pod_zonder_hpa(omgeving):
    """Wat Flux uitrolt, niet alleen wat de values zeggen (#677): één replica, geen HPA en geen PDB.

    Een PDB met één pod blokkeert een node-drain (minAvailable 1) of beschermt niets (maxUnavailable 1).
    """
    documenten = _gerenderd(omgeving)
    soorten = {d["kind"] for d in documenten}
    assert not soorten & {"HorizontalPodAutoscaler", "PodDisruptionBudget"}
    deployment = next(d for d in documenten if d["kind"] == "Deployment")
    assert deployment["spec"]["replicas"] == 1


@pytest.mark.parametrize("omgeving", [p.name for p in _OMGEVINGEN])
def test_stoppen_wacht_eerst_tot_de_ingress_de_pod_loslaat(omgeving):
    """preStop vóór SIGTERM (#677): Kubernetes haalt de pod uit de endpoints terwijl de container nog luistert.

    Zonder die pauze stopt uvicorn met luisteren terwijl Traefik nog verkeer naar de pod stuurt (bij RollingUpdate een
    korte reeks 502's). De pauze, de 45 s van uvicorn en wat uitloop passen samen binnen de termijn.
    """
    deployment = next(d for d in _gerenderd(omgeving) if d["kind"] == "Deployment")
    pod = deployment["spec"]["template"]["spec"]
    commando = pod["containers"][0]["lifecycle"]["preStop"]["exec"]["command"]
    assert commando[0] == "sleep"
    pauze = int(commando[1])
    assert 0 < pauze <= 15
    assert pauze + _uvicorn_termijn() < pod["terminationGracePeriodSeconds"]


def test_zonder_helm_faalt_ci_en_slaat_lokaal_over(monkeypatch):
    """Een CI-image zonder helm mag de chart-tests niet stil overslaan (#768); lokaal blijft het een skip."""
    monkeypatch.setattr("shutil.which", lambda _naam: None)

    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="helm ontbreekt in CI"):
        _helm("version")

    monkeypatch.delenv("CI")
    with pytest.raises(pytest.skip.Exception, match="helm niet geïnstalleerd"):
        _helm("version")


# ── Het sjabloon voor de secret noemt wat de omgeving leest (#856) ──

_SECRET = "onderwijsdata-chat-secrets"


def _secretsleutels(omgeving: Path) -> set[str]:
    """De sleutels die values.yaml met secretKeyRef uit onderwijsdata-chat-secrets leest."""
    return {
        ref["key"]
        for var in _values(omgeving).get("env") or []
        if (ref := (var.get("valueFrom") or {}).get("secretKeyRef")) and ref.get("name") == _SECRET
    }


@pytest.mark.parametrize(
    "omgeving", [p.parent for p in sorted(_ROOT.glob("manifests/*/secret.yaml.example"))], ids=lambda p: p.name
)
def test_secret_sjabloon_noemt_de_sleutels_die_values_lezen(omgeving):
    # Alleen het sjabloon met placeholders; de versleutelde secret.yaml blijft dicht.
    sjabloon = yaml.safe_load((omgeving / "secret.yaml.example").read_text())
    assert sjabloon["metadata"]["name"] == _SECRET
    assert set(sjabloon["stringData"]) == _secretsleutels(omgeving)
    assert set(sjabloon["stringData"].values()) == {"..."}

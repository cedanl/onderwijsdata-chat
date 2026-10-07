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
    # achter een CSV-download niet.
    values = _values(omgeving)
    assert values.get("replicaCount", _CHART["replicaCount"]) == 1
    assert not (values.get("autoscaling") or _CHART["autoscaling"]).get("enabled")

"""
Site-scopefilter (CBS-06) moet dezelfde mbo/hbo/wo-scope geven als het package,
niet een tweede losse definitie (review cluster E).
"""
import json
import re
from pathlib import Path

import onderwijsdata as od

ROOT = Path(__file__).parent.parent


def _site_scope_types() -> set[str]:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    m = re.search(r"const SCOPE_TYPES = \[([^\]]*)\]", html)
    assert m, "SCOPE_TYPES niet gevonden in docs/index.html"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def test_site_scopefilter_gelijk_aan_package_scopeprofiel():
    types = _site_scope_types()
    site = json.loads((ROOT / "docs/data.json").read_text(encoding="utf-8"))
    # isScope in docs/index.html: niet leeg en alle onderwijstypes binnen SCOPE_TYPES
    site_scope = {d["_cbs_id"] for d in site if d["onderwijstype"] and set(d["onderwijstype"]) <= types}
    package_scope = {r["aliases"][0] for r in od.catalog_records()
                     if "supported" in r["scopeprofiel"].values()}
    assert site_scope == package_scope

"""Een catalogusscript laden onder een eigen modulenaam (#910).

De scripts van de CBS-site (`catalogus/cbs/`) en de RIO-site (`catalogus/rio/`) delen namen, zoals
`verrijk_catalogus.py`. Met `import verrijk_catalogus` zou de eerste test in de run bepalen welke van de twee alle
andere tests krijgen; zo heeft elk script zijn eigen naam in `sys.modules`.
"""

import importlib.util
import sys
from pathlib import Path

CATALOGUS = Path(__file__).resolve().parent.parent / "catalogus"


def laad_script(site: str, naam: str):
    map_ = CATALOGUS / site
    if str(map_) not in sys.path:  # de scripts importeren hun eigen hulpmodules (helpers, sector) als top-level
        sys.path.insert(0, str(map_))
    spec = importlib.util.spec_from_file_location(f"catalogus_{site}_{naam}", map_ / f"{naam}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

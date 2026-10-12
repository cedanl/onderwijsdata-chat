"""Manifest per antwoord en rapport (#345): herkomst, geen inhoud.

Een antwoord of rapport droeg geen model-, prompt- of dataversie, en `drop_params`
liet een provider die `seed` niet kent hem stil vallen: of een run herhaalbaar was,
was niet te zien. CBS herziet cijfers en DUO muteert cellen, dus hetzelfde rapport
is morgen een ander getal. Het manifest legt per antwoord en rapport vast met welk
model (en welke providerversie), welke prompt- en catalogusversie, welke appversie
en welke dataversie het is gemaakt, en of seed en temperature daadwerkelijk zijn
toegepast.

Alleen herkomst: er staat geen vraag- of antwoordtekst en geen gebruikersveld in
(privacy-criterium van #345). `seed_toegepast` volgt het contract van de provider
(LiteLLM's capability-lijst, dezelfde die `drop_params` gebruikt); of een provider
een geaccepteerde seed ook echt honoreert, is van buiten niet vast te stellen —
een mislukte lookup is daarom None (onbekend), geen gok.
"""

import hashlib
import logging
import tomllib
from datetime import date
from functools import lru_cache
from pathlib import Path

from litellm import get_supported_openai_params

from config import Config
from core.config import SEED, TEMPERATURE
from tools import store
from tools.catalog import catalogus_digest, catalogus_laatste_update

logger = logging.getLogger(__name__)

_WORTEL = Path(__file__).resolve().parent.parent
_PROMPT = _WORTEL / "prompts" / "system.md"
_PYPROJECT = _WORTEL / "pyproject.toml"
_PERIODESTATUS = "Periodestatus"


@lru_cache(maxsize=1)
def prompt_hash() -> str:
    """Versie van de systeemprompt: hash van prompts/system.md, zoals de
    determinisme-scorekaart (#347) hem ook draagt."""
    return hashlib.sha256(_PROMPT.read_bytes()).hexdigest()[:12]


@lru_cache(maxsize=1)
def app_versie() -> str:
    """De release uit het chart (APP_VERSION), anders pyproject.toml — zoals /version."""
    if Config.APP_VERSION:
        return Config.APP_VERSION
    with open(_PYPROJECT, "rb") as bestand:
        return tomllib.load(bestand)["project"]["version"]


def _sampling(model: str) -> dict:
    """Of seed en temperature dit model bereiken; None als dat niet vast te stellen is."""
    try:
        ondersteund = set(get_supported_openai_params(model=model) or [])
    except Exception as e:
        logger.warning("Sampling-ondersteuning van %s niet vast te stellen: %s", model, e)
        ondersteund = None
    return {
        "seed": SEED,
        "seed_toegepast": None if ondersteund is None else "seed" in ondersteund,
        "temperature": TEMPERATURE,
        "temperature_toegepast": None if ondersteund is None else "temperature" in ondersteund,
    }


def _data_as_of(data_keys) -> list[dict]:
    """Per dataset wat er over haar actualiteit bekend is: de catalogusdatum (CBS), de
    CBS-Periodestatus van de geladen rijen (#180) en een eventuele herlaaddatum (#472)."""
    per_dataset: dict[tuple, dict] = {}
    for key in data_keys:
        known = store.meta(key)
        if known is None:
            continue
        entry = per_dataset.setdefault(
            (known.bron, str(known.dataset)), {"bron": known.bron, "dataset": str(known.dataset)}
        )
        if (
            known.bron == "cbs"
            and "laatste_update" not in entry
            and (update := catalogus_laatste_update(known.dataset))
        ):
            entry["laatste_update"] = update
        df = store.get(key)
        if df is not None and hasattr(df, "columns") and _PERIODESTATUS in df.columns:
            statussen = set(entry.get("periodestatus", ())) | {str(s) for s in df[_PERIODESTATUS].dropna().unique()}
            entry["periodestatus"] = sorted(statussen)
        if known.herladen_op:
            entry["herladen_op"] = known.herladen_op
    return [per_dataset[sleutel] for sleutel in sorted(per_dataset)]


@lru_cache(maxsize=1)
def _catalogus() -> str:
    # De catalogus is vastgepind per proces (uv.lock); één digest volstaat.
    return catalogus_digest()


def bouw(model: str, data_keys, model_versie: str | None = None) -> dict:
    """Het manifest van één antwoord of rapport.

    `model` is wat de app koos; `model_versie` is wat de provider terugmeldde
    (bijv. een gedateerde modelnaam) en staat erbij zodra hij afwijkt.
    """
    m = {
        "model": model,
        "sampling": _sampling(model),
        "prompt_hash": prompt_hash(),
        "catalogus": _catalogus(),
        "app": app_versie(),
        "data_as_of": _data_as_of(data_keys),
        "gemaakt_op": f"{date.today():%d-%m-%Y}",
    }
    if model_versie and model_versie != model:
        m["model_versie"] = model_versie
    return m

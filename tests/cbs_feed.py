"""Een nagebootste CBS-feed voor tests: `tools.cbs.data` in het klein (#841).

De feed filtert vaste rijen zoals de echte bron de `$filter` toepast die `tools/cbs_selectie.py` bouwt: elke
`and`-clausule moet kloppen, een `(… or …)`-groep op één van haar delen, en elke vergelijking heeft de vorm
`trim(Dimensie) eq 'code'` (ADR-006).
"""

from collections.abc import Callable


def _klopt_een(rij: dict, clausule: str) -> bool:
    kolom, _, waarde = clausule.strip("() ").partition(" eq ")
    return str(rij[kolom.removeprefix("trim(").removesuffix(")")]) == waarde.strip("'")


def _klopt(rij: dict, clausule: str) -> bool:
    return any(_klopt_een(rij, deel) for deel in clausule.split(" or "))


def maak_feed(rijen: list[dict]) -> Callable[..., list[dict]]:
    """Een vervanger voor `tools.cbs.data` die uit `rijen` de rijen teruggeeft die bij de `$filter` passen."""

    def feed(dataset_id, **params):
        clausules = [c for c in str(params.get("$filter") or "").split(" and ") if c]
        return [dict(r) for r in rijen if all(_klopt(r, c) for c in clausules)]

    return feed

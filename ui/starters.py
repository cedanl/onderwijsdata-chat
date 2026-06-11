import chainlit as cl

from tools.catalog import _cbs as _cbs_catalog, _rio_duo as _rio_duo_catalog

_TAG_STARTERS: dict[str, tuple[str, ...]] = {
    "Verken Arbeidsmarkt": ("arbeidsmarkt",),
    "Verken Kansengelijkheid": ("kansengelijkheid", "herkomst", "diversiteit"),
    "Verken Regio": ("regio", "gemeente"),
    "Verken Voortijdig Schoolverlaten": ("vsv",),
}


def tag_voorbeeldvragen(tags: tuple[str, ...], n: int = 4) -> list[str]:
    seen: set[str] = set()
    questions: list[str] = []
    for entry in list(_cbs_catalog()) + list(_rio_duo_catalog()):
        if any(t in entry.get("tags", []) for t in tags):
            for q in entry.get("voorbeeldvragen", []):
                if q not in seen:
                    seen.add(q)
                    questions.append(q)
        if len(questions) >= n * 4:
            break
    # spread across the list: pick every k-th to get variety over just the first entries
    step = max(1, len(questions) // n)
    return [questions[i * step] for i in range(n) if i * step < len(questions)]


@cl.set_starters
async def set_starters(user: cl.User | None = None) -> list[cl.Starter]:
    return [
        cl.Starter(
            label="Arbeidsmarkt",
            message="Verken Arbeidsmarkt",
            description="Wat doen afgestudeerden? Aansluiting onderwijs-arbeidsmarkt",  # ty: ignore[unknown-argument]
        ),
        cl.Starter(
            label="Kansengelijkheid",
            message="Verken Kansengelijkheid",
            description="Herkomst, diversiteit en gelijke kansen in het onderwijs",  # ty: ignore[unknown-argument]
        ),
        cl.Starter(
            label="Regio",
            message="Verken Regio",
            description="Regionale verschillen in onderwijsdeelname en -resultaten",  # ty: ignore[unknown-argument]
        ),
        cl.Starter(
            label="Voortijdig Schoolverlaten",
            message="Verken Voortijdig Schoolverlaten",
            description="VSV: wie verlaat school zonder startkwalificatie?",  # ty: ignore[unknown-argument]
        ),
    ]

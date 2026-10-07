"""De Nederlandse getalnotatie: één plek voor grafiek, KPI en controlemeldingen (#418).

37221 wordt 37.221 en 2,1 blijft 2,1: punt voor duizendtallen, komma voor decimalen
(#22). translate() wisselt beide tekens in één doorgang; een tussenteken zoals NUL
kwam eerder als duizendtalscheiding in de grafiek terecht (#378).
"""

_NL = str.maketrans({",": ".", ".": ","})


def nl_getal(waarde: float, decimalen: int | None = None) -> str:
    """Zonder `decimalen`: een geheel getal zonder decimalen, anders één."""
    if decimalen is None:
        decimalen = 0 if float(waarde).is_integer() else 1
    return f"{waarde:,.{decimalen}f}".translate(_NL)

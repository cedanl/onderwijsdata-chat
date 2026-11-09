"""De herkomstregels boven een export: één functie voor de tabel-CSV en de CSV bij een grafiek of kaart (#809).

De CSV bij een grafiek had alleen bron, selecties en afronding (`store.herkomst`); de inhoudshash (#715) en de
md5 van het DUO-bestand (#717) stonden alleen boven de tabel-CSV. Twee paden liepen zo uit elkaar. Wat alleen bij
de tabel-CSV hoort (de herlaadnotitie per gebruiker, de prognosenoot bij afgeronde cellen) blijft in csv_export.
"""

from . import bron_ids, duo, inhoudshash, store

# Wat de CSV zegt als de tabel afgekapt is (BEV-08): in de taal van wie het bestand opent, niet de
# aanwijzing voor de tool (store.ONVOLLEDIG). Een compleet bestand krijgt geen regel: dat is het gewone geval.
ONVOLLEDIG_EXPORT = (
    "Onvolledig bestand: de bron levert deze data in delen en dit bestand bevat alleen het eerste deel. "
    "Aantallen, sommen en totalen die je hieruit berekent, kloppen dus niet."
)


def _hashregels(bron: str, meerdere: bool) -> list[str]:
    """De inhoudshash of DUO-md5 van één geladen tabel; bij meer bronnen met de dataset erbij, anders zijn ze niet uit
    elkaar te houden."""
    known = store.meta(bron)
    welke = f" ({known.dataset})" if meerdere and known is not None else ""
    regels = []
    if inhoud := inhoudshash.hash_van(bron):
        regels.append(
            f"inhoudshash van de brontabel{welke}: {inhoud} (sha256 van df.to_csv(index=False), eerste 12 tekens; "
            "zie docs/reproducibility.md)"
        )
    if known is not None and known.bronhash:
        regels.append(
            f"md5 van het DUO-bestand{welke}: {known.bronhash} (zoals DUO het levert, na te rekenen met md5sum; "
            "zie docs/reproducibility.md)"
        )
    return regels


def herkomstregels(key: str) -> list[str]:
    """Bron, selecties, afronding, inhoudshash of DUO-md5, afkap en onderdrukte cellen van `key`, zonder '#'.

    Over elke geladen tabel achter `key`, niet alleen die van de eerste ouder (#977): een koppeling van SKDB met DUO
    noemt LCSK en de md5 van het DUO-bestand, in welke volgorde het script ze ook las.
    """
    regels = store.herkomst(key)
    bronnen = store.bronkeys(key)
    for bron in bronnen:
        regels += _hashregels(bron, len(bronnen) > 1)
    known = store.meta(key)
    if known is not None and not known.volledig:
        regels.append(ONVOLLEDIG_EXPORT)
    return regels + duo.sentinel_notes(duo.onderdrukt(key), bron_ids.bron_van(key))

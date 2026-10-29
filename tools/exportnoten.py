"""De herkomstregels boven een export: één functie voor de tabel-CSV en de CSV bij een grafiek of kaart (#809).

De CSV bij een grafiek had alleen bron, selecties en afronding (`store.herkomst`); de inhoudshash (#715) en de
md5 van het DUO-bestand (#717) stonden alleen boven de tabel-CSV. Twee paden liepen zo uit elkaar. Wat alleen bij
de tabel-CSV hoort (de herlaadnotitie per gebruiker, de prognosenoot bij afgeronde cellen) blijft in csv_export.
"""

from . import duo, inhoudshash, store

# Wat de CSV zegt als de tabel afgekapt is (BEV-08): in de taal van wie het bestand opent, niet de
# aanwijzing voor de tool (store.ONVOLLEDIG). Een compleet bestand krijgt geen regel: dat is het gewone geval.
ONVOLLEDIG_EXPORT = (
    "Onvolledig bestand: de bron levert deze data in delen en dit bestand bevat alleen het eerste deel. "
    "Aantallen, sommen en totalen die je hieruit berekent, kloppen dus niet."
)


def herkomstregels(key: str) -> list[str]:
    """Bron, selecties, afronding, inhoudshash of DUO-md5, afkap en onderdrukte cellen van `key`, zonder '#'."""
    regels = store.herkomst(key)
    if inhoud := inhoudshash.hash_van(key):
        regels.append(
            f"inhoudshash van de brontabel: {inhoud} (sha256 van df.to_csv(index=False), eerste 12 tekens; "
            "zie docs/reproducibility.md)"
        )
    known = store.meta(key)
    if known is not None and known.bronhash:
        regels.append(
            f"md5 van het DUO-bestand: {known.bronhash} (zoals DUO het levert, na te rekenen met md5sum; "
            "zie docs/reproducibility.md)"
        )
    if known is not None and not known.volledig:
        regels.append(ONVOLLEDIG_EXPORT)
    return regels + duo.sentinel_notes(duo.onderdrukt(key))

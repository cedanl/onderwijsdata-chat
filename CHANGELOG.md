# Changelog

Alle wijzigingen die voor gebruikers of beheerders van belang zijn. Formaat naar
[Keep a Changelog](https://keepachangelog.com/nl/1.1.0/). Versienummers volgen de git-tags;
de laatste tag is 1.8.6.

## Niet uitgebracht

### Betrouwbaarheid van antwoorden
- Getallen, schooljaren en instellingen in een antwoord worden getoetst aan de data van het gesprek.
- Opleidingsvorm en dataset-ID in een antwoord worden getoetst aan de bron.
- De app zet zelf onder een DUO-antwoord wat de bestanden tellen (personen of inschrijvingen) en
  wanneer totalen een ondergrens zijn (-1-cellen in de selectie); de teleenheid-regex is vervallen.
- Grootste daling of stijging komt uit code (`compute_kpi`: `max_drop`, `max_rise`) en niet uit het model.
- DUO-studiejaren hebben een `STUDIEJAAR_LABEL` (2021 = 2021/2022), zodat jaren niet een jaar verschuiven.
- Hoogstens één scopevraag per vraag; daarna redelijke aannames, die het antwoord noemt.
- `run_analysis` weigert overgetypte data en scripts die geen data lezen.
- DUO-teldefinitie en publicatieregels (aantallen 1-4 gepubliceerd als 4) komen uit de riodata-catalogus,
  zonder CKAN-aanroep tijdens het gesprek. Kan de package een beschrijving niet lezen, dan meldt de tool dat.
- Kolomdefinities gelden per DUO-dataset: mbo-opleidingsaanbod krijgt geen hbo-codes VT/DT/DU meer.
- RIO-filters worden vóór het request getoetst aan het filtercontract van RIO, ook enum-waarden en datums;
  de melding noemt de geldige codes (bijv. status `G`, niet `OPEN`).
- Een oorzaak in chat of rapport mag alleen als een eigen dataset haar aantoont (een getal uit een andere
  bron dan het effect); anders staat er dat ze met deze gegevens niet vast te stellen is.
- Heeft een DUO-bestand een teldefinitie, dan schrijft het rapport niet ook een eigen afbakening
  ("buiten beschouwing", "exclusief") naast de brontekst.

### Export en reproduceerbaarheid
- Code-snippets draaien zelfstandig: ze beginnen met de laadstap van de bron, met bron-ID en filters.
- Code-snippets geven dezelfde uitkomst als de app: filters met dezelfde semantiek, DUO-cellen met -1
  uitgesloten, en ook een KPI-snippet laadt zijn eigen data.
- De CSV-export van een grafiek decodeert binaire Plotly-arrays en weigert kapotte figuren met een reden.
- Een herhaalde toolcall toont zijn grafiek niet twee keer.
- Het model gebruikt standaard temperature 0 en een vaste seed (`TEMPERATURE`, `SEED`).

### Gebruikersinterface
- Eén redeneerkaart per antwoord in plaats van een kaart per stap.
- Een vraag tijdens een lopend antwoord krijgt een melding, de getypte tekst blijft staan.
- Een onbekend pad toont een 404-pagina; een uitgeschakelde dashboardroute meldt dat hij nog niet beschikbaar is.
- Hernoem- en verwijderknoppen hebben een `aria-label`.

### Beheer
- De `pytest`-job draait ook `ruff check`; de pipeline blokkeert op falende tests.
- Evaluatie-uitvoer staat niet meer in git.
- riodata is gepind op 0.3.1 (rio-onderwijsdata `c0b4bce`); `/version` noemt de meegebouwde catalogusrevisies.

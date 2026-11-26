---
icon: lucide/circle-help
---

# Veelgestelde vragen

## Waar komen de cijfers vandaan en hoe actueel zijn ze?

Van CBS, DUO, RIO, ROA en UWV, en waar de omgeving ze aanzet ook van de Studiekeuzedatabase. Onder elk antwoord staat het blok **Bronnen**, met een link naar de bronpagina. De pagina **Actualiteit van de bronnen** (`/bronnen`) toont per bron de laatste periode of editie en of het cijfer voorlopig is. Zie [Databronnen begrijpen](databronnen.md).

## Wat betekent "gearchiveerd" bij een CBS-tabel?

Een tabel die CBS niet meer bijwerkt. De app noemt dan de laatste periode, bijvoorbeeld "gearchiveerd, laatste periode 2016/'17". Het UWV-vacaturearchief (peildatum 16-05-2023) heet zo omdat UWV die reeks niet meer maakt; actuele vacatures komen van CBS.

## Waarom zie ik vo-cijfers als ik naar mbo, hbo of wo vroeg?

De chat werkt voor mbo, hbo en wo. Een kleine groep vo-tabellen (negen van CBS en één van DUO) geeft context bij een vraag over vervolgonderwijs, bijvoorbeeld over wie er vanuit het vo doorstroomt. Zie [Databronnen begrijpen](databronnen.md).

## Hoe weet ik of een antwoord klopt?

Code controleert de getallen in het antwoord tegen de opgehaalde data. Je ziet de bronnen, "Let op"-regels en een regel die zegt wat niet gecontroleerd is. Met **Geavanceerd** zie je ook de code achter elke stap. Zie [Een antwoord lezen](betrouwbaarheid.md).

## Wat gebeurt er met mijn vraag en mijn gegevens?

Je vraag en het gesprek gaan naar een externe AI-dienst. De server bewaart gesprekken 90 dagen en rapporten 365 dagen, tenzij je ze eerder verwijdert. Voer geen persoonsgegevens in. Zie [Privacy in gewone taal](privacy.md).

## Kan ik een analyse herhalen of delen?

Ja. Met **Geavanceerd** staat bij elke stap een Python-snippet. Je kunt een gesprek exporteren als Markdown (met Geavanceerd ook als Jupyter-notebook), "Bewijs (JSON)" van een antwoord downloaden, een tabel als CSV downloaden en een rapport downloaden als HTML, Markdown of Word of opslaan als PDF. Zie [Reproduceerbare analyses](../reproducibility.md).

## Welke vragen kan de chat niet beantwoorden?

- Vragen buiten mbo, hbo en wo (po, so en vo), behalve de vo-context hierboven.
- Vragen over individuele studenten of personen: de app gebruikt alleen geaggregeerde data en neemt of ondersteunt geen besluit over een persoon.
- Cijfers die een bron niet publiceert. Een kleine groep (bij DUO 1 tot en met 4) blijft onderdrukt en de app rekent zo'n cel niet terug uit een totaal. Ze zegt dan: "Deze cel is door de bron onderdrukt; terugrekenen geven we niet."

## Waarom staat de pagina Dashboards er niet?

De dashboards staan aan waar de omgeving ze aanzet (`ENABLE_DASHBOARDS`). Op test en playground staan ze aan, op productie uit. Vraag je beheerder.

## Meer hulp

[Problemen oplossen](problemen-oplossen.md). Een fout in de documentatie gevonden? [Open een issue](https://github.com/cedanl/onderwijsdata-chat/issues).

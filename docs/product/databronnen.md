---
icon: lucide/database
---

# Databronnen begrijpen

De app gebruikt alleen open of gelicentieerde bronnen. Per bron staat hier wat erin zit en waar je op let. De technische kant (clients, ID's, uitzonderingen) staat in [Databronnen](../databronnen.md).

| Bron | Wat zit erin | Waar je op let |
|---|---|---|
| **CBS** | 132 datasets met onderwijsstatistieken over mbo, hbo en wo: studenten, diploma's, voortijdig schoolverlaters en meer, uitgesplitst naar diverse dimensies. [Catalogus CBS](https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/) | De chat laadt geen tabellen over po of vo, en geen tabellen over alle onderwijssoorten zonder sectorselectie. |
| **RIO** | Register van onderwijsinstellingen en opleidingen, met sectorfilter op mbo/hbo/wo (8 resources). [Catalogus RIO](https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/) | Een live register: er is geen wijzigingsdatum per register. |
| **DUO** | 15 open datasets over mbo, hbo en wo: prognoses, diplomering, instroom, adressen. [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) | DUO publiceert een aantal van 1 tot en met 4 niet (als -1). De app sluit zulke cellen uit; een som is dan een ondergrens. |
| **ROA** | Arbeidsmarktprognoses per opleidingsniveau en -sector (AIS 2030, de nieuwste editie in de catalogus). | Landelijk, per opleidingsniveau. |
| **Vacatures (CBS)** | 83599NED (openstaand, per provincie en bedrijfstak, per kwartaal) en 85081NED (ontstaan, per beroep, landelijk, per jaar). | Voorlopige kwartalen krijgen een regel "voorlopig cijfer". |
| **UWV** | Open Match vacatures, momentopname van mei 2023. | Een archief: UWV maakt de reeks niet meer. In de chat staat het resultaat met een archiefveld. |
| **Studiekeuzedatabase (LCSK)** | Gelicentieerde data van het Landelijk Centrum Studiekeuze, voor het dashboard Opleidingen. | Geen open data. Alleen op omgevingen waar de sleutel staat (test en playground). |

## Wat "gearchiveerd" betekent

Een gearchiveerde CBS-tabel is een tabel die CBS niet meer bijwerkt. De app zet er dan "gearchiveerd" en de laatste periode bij, bijvoorbeeld "gearchiveerd, laatste periode 2016/'17". Het vacature-archief van UWV (peildatum 16-05-2023) heet zo omdat UWV de reeks niet meer bijwerkt.

## Waarom je soms vo-cijfers ziet

De chat werkt voor mbo, hbo en wo. Daarop is één uitzondering: negen CBS-tabellen en één DUO-dataset over het vo geven context bij een vraag over vervolgonderwijs, bijvoorbeeld wie vanuit het vo naar het mbo, hbo of wo doorstroomt. Die tabellen verschijnen alleen als vo-context ([Vo-context voor vervolgonderwijs](../databronnen.md#vo-context-voor-vervolgonderwijs)).

## Hoe actueel zijn de cijfers?

- Onder elk antwoord staat het blok **Bronnen**. Een CBS-regel noemt de dag waarop CBS de tabel het laatst bijwerkte en de dag waarop de app hem ophaalde.
- De pagina **Actualiteit van de bronnen** (`/bronnen`, link onderaan de startpagina) toont per bron en dataset de laatste periode of editie, de laatste wijziging en of het cijfer voorlopig of definitief is. De app rekent zelf geen verwachte datum uit: noemt de bron er geen, dan staat er "onbekend".
- Een opgehaalde tabel en de CBS-metadata gelden 24 uur.

Zie [Een antwoord lezen](betrouwbaarheid.md) voor wat de regels onder een antwoord betekenen.

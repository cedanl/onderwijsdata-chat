# EU AI-verordening: classificatie per beoogd gebruik

**Status: voorstel van het projectteam (#1025), nog niet bekrachtigd.** Deze notitie legt vast hoe het team
openEDUdata+ onder de EU AI-verordening (Verordening (EU) 2024/1689, "AI Act") indeelt. Het is geen juridisch
advies. Zij is pas definitief als een eigenaar buiten het team haar bekrachtigt (zie [Eigenaar en herbeoordeling](#eigenaar-en-herbeoordeling)).
Zonder die bekrachtiging blijft structureel gebruik door een instelling uitgesloten, samen met de DPIA en de
incidentprocedure (zie [Privacy](privacy.md), Open punten).

## Wat het systeem doet

openEDUdata+ is een AI-assistent voor open Nederlandse onderwijsdata (CBS, DUO, RIO, UWV, ROA). Een gebruiker
stelt een vraag, de app haalt data op uit open bronnen, een taalmodel formuleert het antwoord en de code controleert de
getallen tegen de opgehaalde data (zie [Kwaliteit & veiligheid](kwaliteit-en-veiligheid.md)). Op verzoek maakt de app
een rapport; daarnaast zijn er vaste dashboards. De app gebruikt alleen open, geaggregeerde overheidsdata: geen
gegevens over individuele studenten, geen biometrie.

## Rol

| Rol volgens de verordening | Wie | Opmerking |
|---|---|---|
| Aanbieder (art. 3 lid 3) | CEDA (Npuls), als ontwikkelaar van de app | Het systeem komt onder eigen naam beschikbaar; het onderliggende taalmodel is van een externe AI-aanbieder (zie [Privacy](privacy.md)). |
| Gebruiksverantwoordelijke (art. 3 lid 4) | De deelnemende instelling bij gebruik onder haar gezag | Dezelfde instelling is verwerkingsverantwoordelijke (besluit 19-10-2026, #553). |

Of CEDA ook aanbieder van een model voor algemene doeleinden is, is voor de eigenaar om te beoordelen: de app
bouwt voort op een bestaand model en traint er geen.

## Classificatie per beoogd gebruik

Uitgangspunt: de app is een AI-systeem met beperkt risico. Het is geen hoogrisicosysteem volgens bijlage III en geen
verboden praktijk (art. 5). Bijlage III noemt voor onderwijs (punt 3) systemen voor toelating, het beoordelen van
leerresultaten, het bepalen van het passende onderwijsniveau en het toezicht houden op studenten bij toetsen. De app
doet niets daarvan: zij beantwoordt vragen over geaggregeerde cijfers en neemt of ondersteunt geen besluit over een
persoon.

| Beoogd gebruik | Classificatie (voorstel) | Motivering |
|---|---|---|
| **Demo** (CEDA, geen koppeling met instellingsdata) | Beperkt risico: transparantieplicht art. 50 | Open data, geen besluiten over personen, geen bijlage-III-toepassing. |
| **Onderzoekspilot** (beperkte groep, onder een afspraak met een instelling) | Beperkt risico: art. 50, en art. 4 voor de deelnemers | Zelfde functie als de demo; de instelling treedt op als gebruiksverantwoordelijke. |
| **Structureel gebruik bij een instelling** (beleidsmedewerkers, institutional research) | Beperkt risico, mits de grenzen hieronder gelden | Gebruik voor beleidsinformatie over groepen is geen toelating, beoordeling of toezicht op studenten. Wordt het gebruik uitgebreid naar die functies, dan is de classificatie ongeldig en is een nieuwe beoordeling nodig. |

## Buiten het beoogd gebruik

De app is niet bedoeld voor, en mag niet worden ingezet voor:

- besluiten over individuele studenten of medewerkers: toelating, selectie, beoordeling, advies over een
  onderwijsniveau, studievoortgangs- of uitvalvoorspelling per persoon, toezicht tijdens toetsen;
- besluiten over personeel (werving, beoordeling, ontslag);
- het invoeren van persoonsgegevens: de app waarschuwt daar al voor.

Hoe de app dit nu laat zien: onder het invoerveld staat "Controleer altijd de bronnen bij beleidsbeslissingen" met
de persoonsgegevenswaarschuwing en een link naar de privacytekst. De bron- en scopegrenzen (alleen mbo/hbo/wo, alleen
open geaggregeerde data) volgen uit de tools, niet uit een tekst. Een uitdrukkelijke zin dat de app niet voor
besluiten over personen is bedoeld, staat nog niet in de app (zie [Open punten](#open-punten)).

## Transparantie (art. 50) en AI-geletterdheid (art. 4)

| Onderdeel | Stand |
|---|---|
| De gebruiker weet dat hij met een AI-systeem praat (art. 50 lid 1) | De app heet "AI-assistent" in de productomschrijving en de rapportregel, maar de chat zelf zegt het niet in een vaste, zichtbare zin. **Nog te toetsen en zo nodig toe te voegen.** |
| Door AI gemaakte tekst is herkenbaar (art. 50 lid 2) | Een rapport krijgt de regel "Opgesteld met openEDUdata+ (AI-assistent)", met de naam van de gebruiker als die er is (#748). Voor antwoorden in de chat geldt hetzelfde als hierboven. |
| Bronnen en controle | Antwoorden tonen de bronnen en de gecontroleerde getallen; het onderschrift vraagt de bronnen te controleren (zie [Kwaliteit & veiligheid](kwaliteit-en-veiligheid.md)). Dit is geen eis uit art. 50 maar ondersteunt hem. |
| AI-geletterdheid (art. 4) | De verplichting ligt bij aanbieder en gebruiksverantwoordelijke. Bij structureel gebruik zorgt de instelling voor instructie van haar gebruikers; CEDA levert daarvoor de uitleg in deze documentatie. Een korte gebruikersinstructie is nog niet geschreven. |

## Open punten

- Bekrachtiging van deze classificatie en rolverdeling door de eigenaar buiten het team.
- Toetsen of de chat in beeld al duidelijk zegt dat de antwoorden van een AI komen, en dat zo nodig toevoegen.
- Een zin in de app of de privacytekst dat het systeem niet voor besluiten over personen is bedoeld.
- Een korte instructie voor gebruikers van een instelling (art. 4).
- Het onderliggende taalmodel en de modelaanbieder: de verplichtingen van die aanbieder vallen buiten deze notitie.

## Eigenaar en herbeoordeling

| | |
|---|---|
| Opgesteld door | Projectteam openEDUdata+ (CEDA), november 2026 |
| Eigenaar buiten het team | **Nog aan te wijzen** (bijvoorbeeld de FG of juridisch adviseur van de deelnemende instelling of van Npuls) |
| Bekrachtigd op | Nog niet |
| Herbeoordeling | Uiterlijk twaalf maanden na bekrachtiging, en eerder bij: een nieuw beoogd gebruik, gebruik voor een bijlage-III-functie, koppeling met gegevens over individuele studenten, of een ander taalmodel of andere aanbieder |

Verwant: [Privacy](privacy.md), [EduGenAI-koppeling](edugenai.md), [Kwaliteit & veiligheid](kwaliteit-en-veiligheid.md).
Besluiten: #553 (verwerkingsverantwoordelijke), #711 (afspraken met Npuls).

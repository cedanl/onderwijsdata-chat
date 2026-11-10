# Privacy-informatie

Hoe openEDUdata+ met je gegevens omgaat. Dit beschrijft de werking van de demoversie; de formele
privacyverklaring volgt zodra de open punten onderaan zijn vastgesteld. Dezelfde tekst staat in de app op
`/privacy`, bereikbaar vóór het inloggen (link op de loginpagina, in de voettekst, onder het invoerveld en in
de instellingen). Op die plekken toont de app de tekst als popup; `/privacy` blijft de volledige pagina.
`frontend/src/__tests__/privacyPage.test.js` bewaakt dat de kopjes hier en in de app gelijk
blijven.

## Wat naar de AI-dienst gaat

- Je vraag, de eerdere berichten van het gesprek, je instelling en functie uit je profiel en de opgehaalde data
  gaan naar een externe AI-dienst die het antwoord formuleert. Koos je zelf geen instelling, dan is dat de
  instelling die je SRAM-account opgeeft, als de app die kent; de kop toont welke het is (#777). Welke dienst en welk model dat is, staat onder het
  invoerveld; op de omgevingen van SURF is dat Microsoft Azure AI Foundry met een Claude-model (`MODEL` in
  `manifests/<omgeving>/values.yaml`).
- De cijfers zelf komen van open bronnen (CBS, DUO en RIO). Daarheen gaat alleen de opvraag (welke tabel, welke
  selectie), niets over de gebruiker.
- Voer geen persoonsgegevens in. De app herkent een BSN (elfproef), een e-mailadres en een Nederlands
  telefoonnummer en waarschuwt dan, maar blokkeert niet en maskeert niet; een naam herkent zij niet
  (`frontend/src/persoonsgegevens.js`, `core/persoonsgegevens.py`, #478). Verstuur je de vraag toch, dan gaat de
  tekst met die gegevens naar de AI-dienst en blijft hij staan in het gesprek op de server, in de kopie in je
  browser en in een export van het gesprek, tot je het gesprek verwijdert; alleen de titel van het gesprek wordt
  gemaskeerd (besluit 19-10, #616).

## Wat de server bewaart

Per account, in `persistence/db.py` (SQLite lokaal, PostgreSQL op SDP):

| Gegevens | Tabel | Tot wanneer |
|---|---|---|
| Gesprekken: vraag, antwoord, toolstappen, titel | `conversations` | 90 dagen na het laatste bericht in het gesprek; eerder als de gebruiker het gesprek of al zijn gegevens verwijdert |
| Rapporten en dashboards (werkboeken) | `workbooks` | 365 dagen nadat het werkboek voor het laatst is opgeslagen of geopend; eerder als de gebruiker het onder Rapporten of al zijn gegevens verwijdert. Het verwijderen van een gesprek laat ze staan (#513) |
| Feedback op rapporten en dashboards, inclusief de antwoorden over de eigen instelling, de instelling uit het profiel in de app (naam, kolom `instelling`: de gekozen instelling of anders die van het SRAM-account, #777; leeg als er geen is) en eventueel achtergelaten contactgegevens (vrije tekst). De vragen over de eigen instelling worden alleen na een eigen keuze van de gebruiker gesteld (knop Help ons verder); de rapportvragen zijn zonder die vragen te versturen (#666) | `feedback` | 90 dagen na het geven; eerder als de gebruiker al zijn gegevens verwijdert |
| Algemene feedback via de link Feedback: tekst, soort en pagina (#600) | `algemene_feedback` | 90 dagen na het versturen; eerder als de gebruiker al zijn gegevens verwijdert |
| Datarecepten: hoe een tabel is opgehaald | `data_recipes` | gaan weg met het gesprek (ook bij de opschoning) of met al zijn gegevens; een recept zonder gesprek na 90 dagen |
| Bewijs per antwoord: welke bron en selectie de data van een antwoord had, de uitkomsten van berekeningen en de kolommen van kaarten, onder de hash van de antwoordtekst (ADR-009); niet de vraag of het antwoord zelf | `beurtbewijs` | gaat weg met het gesprek (ook bij de opschoning) of met al zijn gegevens; een rij zonder gesprek na 90 dagen |
| Ingetrokken sessies, als hash | `revoked_tokens` | tot de sessie verloopt |
| Na "verwijder al mijn gegevens": de accountnaam als hash, zodat geen enkele sessie van vóór dat moment nog geldt (#786) | `revoked_users` | tot elke sessie van vóór het verwijderen verlopen is (standaard 24 uur) |

Een oordeel op een antwoord (👍/👎 met toelichting en een kopie van vraag, antwoord en stappen) bewaart de server sinds
9 november 2026 niet meer: de knoppen zijn weg en wat er stond, is bij de volgende start van de app verwijderd (#983).

Inloggen: met `CHAT_USERS` (gebruikersnaam en wachtwoord) bewaart de server alleen de gebruikersnaam bij de
gegevens. Met SURF SRAM is het e-mailadres de accountnaam, ook als auteur van een rapport (#487); naam,
organisatie en instelling staan tijdens de sessie in het geheugen van de server (begrensd, ten hoogste
`SESSION_MAX_HOURS`).

Bewaartermijn (#485, besluit 21-10-2026): elke nacht verwijdert een geplande taak wat over zijn termijn is
(`python -m persistence.opschonen`, een CronJob in de Helm-chart; aan op test en playground, niet op productie). De
termijnen staan in de tabel hierboven: gesprekken en feedback 90 dagen, rapporten en dashboards 365 dagen, langer
omdat een rapport het resultaat is dat je bewaart en terugkijkt. Ze zijn in te stellen met
`BEWAARTERMIJN_GESPREKKEN_DAGEN` en `BEWAARTERMIJN_RAPPORTEN_DAGEN`; een ongeldige waarde of een termijn onder de 7
dagen verwijdert niets. De serverlogs en de back-ups van de beheerder vallen buiten deze opschoning.

## Wat in je browser staat

- `localStorage`: een kopie van de gesprekken en het lopende gesprek, de werkboeken, de dashboardchat, het profiel
  (instelling, functie, weergave) en het sessietoken. Uitloggen wist dit alles (`SESSION_DATA_KEYS` en het profiel,
  `frontend/src/App.jsx`), en "Verwijder al mijn gegevens" ook.
- `openEDUdata_recent` (#603): de ID's van de gesprekken en rapporten die deze browser het laatst opende, en van de
  favoriete rapporten; geen titels of inhoud. Blijft na uitloggen staan (`NOT_SESSION_DATA_KEYS`): de chat en
  `/rapporten` tonen een ID alleen als het bij een gesprek of rapport van het ingelogde account hoort.
- `openEDUdata_te_verwijderen` (#801): de ID's van verwijderde gesprekken waarvan de server de verwijdering nog niet
  bevestigde; geen titels of inhoud. Hoort bij het account (`SESSION_DATA_KEYS`): uitloggen stuurt die verwijderingen
  eerst nog met het eigen token, en uitloggen, een nieuwe login en het einde van de sessie wissen de lijst.
- Een sessie duurt `SESSION_TTL_HOURS` (8 uur) en wordt bij gebruik verlengd tot `SESSION_MAX_HOURS` (24 uur) na het
  inloggen. Tijdens het inloggen met SRAM staat er kort een cookie met de OIDC-state; verder gebruikt de app geen
  cookies en geen analytics.

## Het logboek

Op INFO en hoger staan van een vraag, een antwoord, toolargumenten en fouttekst alleen de lengte en een hash in het
log (`core.logging_util.tekst_kenmerk`, #475, #502), naast tijdstippen, toolnamen en het model. Alleen op DEBUG,
dat niet standaard aanstaat, staat tekst in het log (SECURITY.md S19). De bewaartermijn van het logplatform van SDP
is een open punt.

## Wat je zelf kunt doen

- Een gesprek verwijderen in de gesprekslijst; een rapport verwijderen onder Rapporten, een dashboard uit de
  verwijderde dashboardbouwer onder Dashboards (waar de omgeving die pagina aanzet, #765). Een gesprek heeft
  8 s bedenktijd ("Ongedaan maken", #493); pas daarna gaat de verwijdering naar de server. Log je binnen die tijd uit,
  dan gaat ze meteen, nog met je login, en wordt de login pas daarna ingetrokken (#778). Lukt de verwijdering op de
  server niet, dan staat het gesprek, rapport of dashboard weer in de lijst, met een melding en "Opnieuw proberen".
  Sluit je binnen de bedenktijd de tab, dan gaat de verwijdering zonder melding mee met het sluiten. Tot de server een
  verwijderd gesprek bevestigt, onthoudt deze browser het ID ervan (#801). Mislukte de verwijdering, dan gaat ze bij je
  volgende bezoek aan de chat opnieuw, en tot dat gelukt is staat het gesprek niet in de lijst; lukt het dan weer niet,
  dan volgt dezelfde melding. Stel je na het verwijderen nog een vraag in het gesprek, dan blijft het bewaard. Log je
  uit, dan gaan ook deze verwijderingen eerst nog met je login. Is je sessie bij je volgende bezoek verlopen, dan is het
  ID gewist en staat het gesprek na het inloggen weer in de lijst; verwijder het dan opnieuw.
- Een gesprek exporteren als Markdown en de tabel achter een antwoord downloaden als CSV (`/api/data/csv`).
- Al je gegevens in één keer exporteren: in de instellingen met "Exporteer al mijn gegevens"
  (`/api/mijn-gegevens/export`, #645). Je krijgt één JSON-bestand met je gesprekken, rapporten en dashboards, feedback,
  datarecepten en het bewijs per antwoord. Niet erin: wat alleen in je browser staat.
- Al je gegevens in één keer verwijderen: in de instellingen met "Verwijder al mijn gegevens"
  (`DELETE /api/mijn-gegevens`, #646), nadat je het woord "verwijder" hebt getypt. Dat kan niet ongedaan worden
  gemaakt; exporteer eerst. Dan verdwijnen in één transactie alle rijen van je account uit de tabellen hierboven
  (gesprekken, rapporten en dashboards, al je feedback, datarecepten en het bewijs per antwoord), en
  ook de kopie in deze browser; je wordt uitgelogd en al je sessies worden ingetrokken, ook die op een ander apparaat
  (#786): een open chat daar sluit bij de volgende vraag. Wat blijft: de serverlogs (zonder gesprekstekst, #475) en de
  back-ups van de beheerder, de hash van je accountnaam in `revoked_users` tot je laatste sessie verlopen is, de hash
  van een sessie waarmee je uitlogde in `revoked_tokens` tot zij verloopt, en de kopie in de browser van een ander
  apparaat tot je daar uitlogt. Gebruik je een gedeeld account (zoals `demo` of een
  teamaccount in `CHAT_USERS`), dan verdwijnt ook het werk van de anderen. Zonder eigen login (iedereen is dan
  `gast`) kan het niet: de knop ontbreekt en de server antwoordt 404.

## Verantwoordelijke en contact

openEDUdata+ is een project van CEDA (Npuls). De verwerkingsverantwoordelijke is de deelnemende instelling
(besluit 19-10-2026, #553). Met een privacyvraag kan een gebruiker terecht bij die instelling: bij de
privacycontactpersoon of de functionaris gegevensbescherming (FG) van de instelling. Het projectteam van CEDA is er
alleen voor vragen over de demo zelf.

## Open punten

Te beantwoorden door het team of de functionaris gegevensbescherming vóór de tekst definitief is (#477). Over de
verwerkingsverantwoordelijke is besloten (#553, 19-10-2026; zie hierboven). Open blijven:

- Verwerkersovereenkomst met de AI-aanbieder, de regio van het eindpunt en de afspraak dat invoer niet wordt
  bewaard of gebruikt voor training.
- De bewaartermijn van het logplatform en van de back-ups van SDP; die van de gegevens in de app staat hierboven
  (#485).
- Of er een DPIA nodig is.

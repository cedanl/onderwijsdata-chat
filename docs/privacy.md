# Privacy-informatie

Hoe openEDUdata+ met je gegevens omgaat. Dit beschrijft de werking van de demoversie; de formele
privacyverklaring volgt zodra de open punten onderaan zijn vastgesteld. Dezelfde tekst staat in de app op
`/privacy`, bereikbaar vóór het inloggen (link op de loginpagina, in de voettekst, onder het invoerveld en in
de instellingen). `frontend/src/__tests__/privacyPage.test.js` bewaakt dat de kopjes hier en in de app gelijk
blijven.

## Wat naar de AI-dienst gaat

- Je vraag, de eerdere berichten van het gesprek, je instelling en functie uit je profiel en de opgehaalde data
  gaan naar een externe AI-dienst die het antwoord formuleert. Welke dienst en welk model dat is, staat onder het
  invoerveld; op de omgevingen van SURF is dat Microsoft Azure AI Foundry met een Claude-model (`MODEL` in
  `manifests/<omgeving>/values.yaml`).
- De cijfers zelf komen van open bronnen (CBS, DUO en RIO). Daarheen gaat alleen de opvraag (welke tabel, welke
  selectie), niets over de gebruiker.
- Voer geen persoonsgegevens in. De app herkent een BSN (elfproef), een e-mailadres en een Nederlands
  telefoonnummer en waarschuwt dan, maar blokkeert niet; een naam herkent zij niet
  (`frontend/src/persoonsgegevens.js`, `core/persoonsgegevens.py`, #478).

## Wat de server bewaart

Per account, in `persistence/db.py` (SQLite lokaal, PostgreSQL op SDP):

| Gegevens | Tabel | Tot wanneer |
|---|---|---|
| Gesprekken: vraag, antwoord, toolstappen, titel | `conversations` | tot de gebruiker het gesprek verwijdert |
| Rapporten en dashboards (werkboeken) | `workbooks` | tot de gebruiker ze onder Rapporten verwijdert; het verwijderen van een gesprek laat ze staan (#513) |
| Feedback op rapporten en dashboards | `feedback` | onbepaald |
| Feedback per antwoord: duim, toelichting en een kopie van vraag, antwoord en stappen (`trace`) | `answer_feedback` | onbepaald; bij het verwijderen van het gesprek losgekoppeld van account en gesprek (#476) |
| Datarecepten: hoe een tabel is opgehaald | `data_recipes` | gaan weg met het gesprek |
| Ingetrokken sessies, als hash | `revoked_tokens` | tot de sessie verloopt |

Inloggen: met `CHAT_USERS` (gebruikersnaam en wachtwoord) bewaart de server alleen de gebruikersnaam bij de
gegevens. Met SURF SRAM is het e-mailadres de accountnaam, ook als auteur van een rapport (#487); naam,
organisatie en instelling staan tijdens de sessie in het geheugen van de server (begrensd, ten hoogste
`SESSION_MAX_HOURS`). Er is nog geen automatische opschoning of bewaartermijn (#485).

## Wat in je browser staat

- `localStorage`: een kopie van de gesprekken en het lopende gesprek, de werkboeken, de dashboardchat, het profiel
  (instelling, functie, weergave) en het sessietoken. Uitloggen wist dit alles (`SESSION_DATA_KEYS` en het profiel,
  `frontend/src/App.jsx`).
- Een sessie duurt `SESSION_TTL_HOURS` (8 uur) en wordt bij gebruik verlengd tot `SESSION_MAX_HOURS` (24 uur) na het
  inloggen. Tijdens het inloggen met SRAM staat er kort een cookie met de OIDC-state; verder gebruikt de app geen
  cookies en geen analytics.

## Het logboek

Op INFO en hoger staan van een vraag, een antwoord, toolargumenten en fouttekst alleen de lengte en een hash in het
log (`core.logging_util.tekst_kenmerk`, #475, #502), naast tijdstippen, toolnamen en het model. Alleen op DEBUG,
dat niet standaard aanstaat, staat tekst in het log (SECURITY.md S19). De bewaartermijn van het logplatform van SDP
is een open punt.

## Wat je zelf kunt doen

- Een gesprek verwijderen in de gesprekslijst; een rapport of dashboard verwijderen onder Rapporten.
- Een gesprek exporteren als Markdown en de tabel achter een antwoord downloaden als CSV (`/api/data/csv`).
- Al je gegevens in één keer verwijderen of exporteren kan nog niet (#485).

## Verantwoordelijke en contact

openEDUdata+ is een project van CEDA (Npuls). Wie de verwerkingsverantwoordelijke is en bij wie een gebruiker
terechtkan met een privacyvraag, wordt vastgesteld vóór de demofase eindigt; tot die tijd via het projectteam van
CEDA.

## Open punten

Te beantwoorden door het team of de functionaris gegevensbescherming vóór de tekst definitief is (#477):

- Verwerkingsverantwoordelijke (Npuls, SURF of de instelling), contactpunt en functionaris gegevensbescherming.
- Verwerkersovereenkomst met de AI-aanbieder, de regio van het eindpunt en de afspraak dat invoer niet wordt
  bewaard of gebruikt voor training.
- Bewaartermijn per gegevenssoort, opschoning, en in één keer alles verwijderen of exporteren (#485).
- Of er een DPIA nodig is.

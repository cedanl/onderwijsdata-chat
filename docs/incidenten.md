---
icon: lucide/triangle-alert
---

# Incidenten en datalekken

Wat je doet als de app stuk is, fout antwoordt, wordt aangevallen of gegevens laat zien aan wie ze niet mogen zien.
De techniek (probes, logs, uitrol) staat in [Operatie](operatie.md); back-up en herstel in #683, monitoring en alerts
in #678. Deze pagina beschrijft rollen, meldroute en stappen (audit F-17, #1026).

**Stand:** de procedure is beschreven maar nog niet geoefend en de rollen zijn nog niet met namen ingevuld (zie
[Nog open](#nog-open)). Er is nog geen alarmering (#678): een incident komt nu binnen via een gebruiker, een
beheerder die het log leest of een melding van de instelling.

## Soorten incident

| Soort | Voorbeeld | Ernstig als ... |
|---|---|---|
| Storing | pod start niet, `/ready` geeft 503, bron of model onbereikbaar | langer dan een werkdag, of een les of demo staat stil |
| Onjuiste antwoorden op schaal | een bron- of promptwijziging laat veel antwoorden fout of zonder bron uitvallen | meerdere gebruikers of instellingen melden hetzelfde |
| Beveiligingsincident | uitgelekt secret of API-sleutel, misbruik van login, ongeautoriseerde toegang tot de omgeving | het secret echt buiten het team is gekomen |
| Datalek | een gesprek, rapport of dashboard zichtbaar voor een ander account; persoonsgegevens in een log, export of back-up bij een onbevoegde | altijd: begin direct met de meldroute hieronder |

Twijfel je tussen twee soorten, behandel het als de zwaarste. Een datalek is elke inbreuk op persoonsgegevens
(vernietiging, verlies, wijziging of toegang door een onbevoegde), ook als het per ongeluk gebeurde.

## Rollen

De verwerkingsverantwoordelijke is de deelnemende instelling (#553); het team van de app is verwerker voor haar
gebruikers. Het team beslist daarom over het indammen, de instelling over de melding aan de Autoriteit
Persoonsgegevens (AP) en aan betrokkenen.

| Rol | Taak | Invulling |
|---|---|---|
| Melder | merkt het op (gebruiker, beheerder, reviewer) en meldt het direct bij de incidentcoördinator | iedereen |
| Incidentcoördinator | beslist over soort en ernst, dammen in, houdt het logboek bij, meldt bij de instelling | een teamlid van de app; vervanger vooraf benoemd |
| Technisch beheerder | voert de stappen hieronder uit (schalen, roteren, intrekken, logs) | teamlid met toegang tot de kubeconfig |
| Contactpersoon instelling | ontvangt de melding namens de verwerkingsverantwoordelijke en beslist over de melding aan de AP | functionaris gegevensbescherming of privacycontact van de instelling |
| Platform (SDP) | herstelt de database uit een back-up, kijkt in platformlogs | via het supportkanaal van SDP |

**Namen, telefoonnummers en de ticketroute staan niet in de repo.** Ze staan in de afgesproken ruimte van het team
(besloten wiki of kluis van de organisatie), met een vervanger per rol. Controleer ze bij elke oefening en bij elke
wissel in het team.

## Meldplicht

- **Binnen 72 uur** na ontdekking meldt de verwerkingsverantwoordelijke een datalek bij de AP (AVG art. 33), tenzij
  het onwaarschijnlijk is dat het een risico voor de betrokkenen inhoudt.
- **Zonder onredelijke vertraging** meldt de verwerker het datalek aan de verwerkingsverantwoordelijke (art. 33
  lid 2). Voor ons: zodra de incidentcoördinator vaststelt dat het om persoonsgegevens gaat, meldt hij dat aan de
  contactpersoon van de instelling. Wacht niet tot de oorzaak bekend is, en reken de 72 uur vanaf onze ontdekking.
- Is er waarschijnlijk een hoog risico voor betrokkenen, dan informeert de instelling ook hen (art. 34).
- Elk datalek, ook een dat niet gemeld hoeft te worden, komt in het logboek met feiten, gevolgen en genomen
  maatregelen (art. 33 lid 5).

De melding bevat minimaal: wat er gebeurd is, welke gegevens (soort, aantal accounts of rijen bij benadering), sinds
wanneer en tot wanneer, wat al gedaan is en wie het aanspreekpunt is. Een voorlopige melding met "nog onbekend" is
beter dan een late.

## Stappen per soort

Altijd in deze volgorde: **indammen, vastleggen, melden, nazorg**. Houd een logboek met tijdstip, wie, wat. Zet geen
gesprekstekst of persoonsgegevens in het logboek of in een issue; verwijs naar fout-ID, verbindings-ID of rij-ID.

### Storing

1. Indammen: `curl …/ready` en `kubectl get pods,helmrelease` (zie het [runbook](operatie.md#runbook)); een foute
   release zet je terug door de pin in `manifests/playground/helmrelease.yaml` terug te draaien (zie
   [promoten](promoten.md)).
2. Vastleggen: tijdstip, fout-ID's, logregels.
3. Melden: bij een storing langer dan een werkdag laat de coördinator de instellingen weten dat de app niet bereikbaar
   is. Dit is geen datalek.
4. Nazorg: issue met oorzaak en maatregel; ontbrekende alerts naar #678, ontbrekende herstelstap naar #683.

### Onjuiste antwoorden op schaal

1. Indammen: bepaal welke bron, tool of release de oorzaak is. Zet bij een verkeerde release de vorige terug; is een
   bron de oorzaak, dan staat die in de bronstatus van de app ([operatie](operatie.md#bronstatus-in-de-app-1057)).
   Is niets te herstellen, schaal dan naar 0 (zie Datalek) in plaats van onjuiste cijfers te laten staan.
2. Vastleggen: voorbeelden met fout-ID of verbindings-ID, en de feedbackrijen die erover gaan.
3. Melden: aan de instellingen die de app gebruikt hebben, met de periode waarin antwoorden onbetrouwbaar waren.
4. Nazorg: een test of eval-geval dat dit vangt; een correctie in de changelog.

### Beveiligingsincident

1. Indammen:
   - **Secret uitgelekt:** roteer het in `manifests/<omgeving>/secret.yaml` (SOPS, zie `Agents.md` en de skill
     `sdp-secrets-management`), laat Flux uitrollen en herstart de pod (`kubectl rollout restart
     deploy/fn-onderwijsdata-chat -n services-onderwijsdata-chat`). Een LLM-sleutel trek je ook bij de aanbieder in;
     een sleutel uit `MCP_API_KEYS` haal je uit de lijst ([mcp](mcp.md)).
   - **Misbruikt account:** trek alle tokens van dat account in via `revoked_users` (`sha256(gebruikersnaam)` met het
     huidige moment; een login daarna werkt weer, zie `SECURITY.md`, #786) en wijzig of verwijder het wachtwoord in
     `CHAT_USERS`. Voor een SRAM-account blokkeert de instelling het account.
   - **Onbekende oorzaak of actief misbruik:** schaal de app naar 0 (zie Datalek).
2. Vastleggen: bewaar de logregels van de periode (`kubectl logs`, ook `--previous`) buiten de pod, voordat ze
   verdwijnen.
3. Melden: raakt het persoonsgegevens, volg dan de route van een datalek.
4. Nazorg: oorzaak weghalen, `SECURITY.md` bijwerken, wijziging vastleggen in een issue.

### Datalek

1. Indammen: stop de bron van het lek. Is een gesprek of rapport zichtbaar voor een ander account (bijvoorbeeld een
   gedeeld account of een fout in de eigenaarscontrole), zet dan de app uit tot de oorzaak bekend is:
   ```bash
   kubectl --context <omgeving> -n services-onderwijsdata-chat scale deploy/fn-onderwijsdata-chat --replicas=0
   ```
   Flux kan dit bij de volgende reconcile terugzetten; pauzeer daarom ook de HelmRelease (`flux suspend helmrelease`)
   of laat het platformteam dat doen. Terugzetten pas na besluit van de incidentcoördinator.
2. Vastleggen: wat was zichtbaar voor wie en hoe lang; welke tabellen (`conversations`, `workbooks`, `feedback`,
   `algemene_feedback`, `data_recipes`); welke accounts. Gebruik log- en verbindings-ID's, geen inhoud.
3. Melden: direct aan de contactpersoon van de instelling (zie Meldplicht), schriftelijk, met tijdstip. De instelling
   beslist over de AP en de betrokkenen; wij leveren de feiten en helpen met export of verwijdering van gegevens.
4. Nazorg: de oorzaak herstellen met een test die het lek vangt, een nabespreking binnen twee weken, en
   `SECURITY.md` en [privacy](privacy.md) bijwerken als de gegevensstroom verandert.

## Route van feedback "fout antwoord" naar een beheerder (T09)

Feedback komt in de tabellen `feedback` (op rapporten en dashboards) en `algemene_feedback` (de link Feedback), zie
[privacy](privacy.md). Er is **geen beheerdersscherm en geen melding bij nieuwe feedback**, en de tabellen hebben geen
statuskolom: wie een rij niet leest, ziet haar niet. Daarom de afspraak:

| Vraag | Afspraak |
|---|---|
| Wie leest | de technisch beheerder van de week (rooster in de besloten ruimte van het team) |
| Hoe vaak | elke werkdag tijdens een les of pilot; anders minstens wekelijks |
| Hoe | alleen-lezen query op de database via het platform, op `created_at` van de laatste periode; na 90 dagen verdwijnen rijen (#485) |
| Wanneer een issue | één melding over een feitelijk onjuist antwoord: een issue met fout-ID of rapport-ID, zonder gesprekstekst. Dezelfde klacht van twee accounts of meer: soort "onjuiste antwoorden op schaal", de coördinator beslist |
| Wanneer een incident | feedback die meldt dat iemand andermans gegevens zag: direct de procedure Datalek |
| Terugkoppeling | de app toont geen reactie; de beheerder reageert alleen via contactgegevens die de gebruiker zelf heeft achtergelaten |

Contactgegevens in feedback zijn vrije tekst en persoonsgegevens: kopieer ze niet naar issues.

## Oefening

Eén tabletop per jaar en na elke grote wijziging van de rollen, 60 minuten, met de coördinator, een technisch
beheerder en bij voorkeur de contactpersoon van een instelling. Scenario voor de eerste oefening: een gebruiker meldt
via Feedback dat zij in haar lijst met rapporten een rapport van een ander ziet.

Toets: wordt het als datalek herkend, wie wordt wanneer gebeld, gaat de melding aan de instelling binnen één werkdag
weg, wie schaalt naar 0 en wie zet de app terug. Leg de uitkomst vast, met verbeterpunten als issues.

| Datum | Scenario | Uitkomst |
|---|---|---|
| nog te plannen | rapport van een ander account zichtbaar | |

## Nog open

- Rollen met namen en vervangers invullen, en benoemen waar de contactgegevens staan.
- De eerste oefening plannen en de datum hierboven invullen.
- Alerting (#678), back-up en herstel met RPO/RTO (#683) en een beheerderszicht op feedback (met status) zijn nog niet
  gebouwd; tot dan geldt de handmatige route hierboven.

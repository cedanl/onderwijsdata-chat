---
icon: lucide/plug
---

# API Referentie

De app draait op FastAPI en biedt een REST-API en WebSocket-endpoint voor communicatie met het frontend.

---

## Wat is stabiel

Niet elke interface is bedoeld om op te bouwen. De meegeleverde frontend draait altijd op dezelfde release als de server en
kent dus geen versieverschil; een andere client of een ander team heeft aan een kleiner, vast deel genoeg.

| Interface | Status | Waar je op kunt rekenen | Waar niet |
|---|---|---|---|
| `GET /health`, `/ready` | **stabiel** | Pad, methode en statuscode; `/health` geeft `{"status": "ok"}`. Kubernetes en de deploycontrole leunen erop. | Extra velden in de body. |
| `GET /version` | **stabiel** | De sleutels die bij `/version` hieronder staan; nieuwe sleutels komen erbij, bestaande verdwijnen niet. | Volgorde van sleutels. |
| MCP-server ([MCP](mcp.md)) | **stabiel** | Toolnamen, parameters, de envelope van `search_catalog` (`status`, `kandidaten`, `melding`, `vervolgstap`) en in elk resultaat de sleutels van `bewijs` (ook die in `kwaliteit`) en `vervolg` ([Bewijs en vervolg](mcp.md#bewijs-en-vervolg)); de naam van de prompt en resource `bronregels`. | De inhoud van `kandidaten` en de catalogus zelf: die volgt de bronnen; de tekst van `bronregels`, die de domeinregels volgt. |
| Deep link `/chat#vraag=…` ([hieronder](#deep-link-naar-de-chat)) | **stabiel** | Pad en parameter: de vraag staat na het openen, ook na het inloggen, in de invoer van een nieuw gesprek en wordt niet vanzelf verstuurd. | Hoe de app de vraag schoont en de grens van 500 tekens. |
| Manifest bij een antwoord of rapport | **stabiel** | De bestaande sleutels (model, sampling, prompt-hash, catalogus, dataversie). | Nieuwe sleutels komen erbij zonder aankondiging. |
| Reproduceerbare snippet ([Reproduceerbare analyses](reproducibility.md)) | **stabiel in doel** | Hij laadt dezelfde bron met dezelfde filters en geeft dezelfde bewerkingen. | De exacte codetekst, en dat een bron later hetzelfde getal geeft (CBS herziet, DUO muteert cellen). |
| Alle overige `/api/*`-eindpunten en het WebSocket-protocol van `/api/chat` | **intern** | Alleen dat de frontend van dezelfde release werkt. | Alles; kan zonder aankondiging wijzigen. |
| Toolschema's voor het model (`tools/schemas.py`) en het `data_key`-formaat | **intern contract** | De keten `data_key` → filter → KPI/grafiek, bewaakt door `tests/test_tool_schema_contract.py` en `tests/test_tool_keten_contract.py`. | Het formaat van een `data_key`: behandel hem als ondoorzichtig, ook al ziet hij er leesbaar uit. |

**Wat telt als breaking change** in een stabiele interface: een pad, methode, toolnaam, parameter of sleutel die verdwijnt
of een andere naam krijgt; een betekenis die verandert; een optionele parameter die verplicht wordt. Een nieuwe tool, een
nieuwe optionele parameter of een nieuwe sleutel in een antwoord is dat niet.

**Wat je dan doet:** open eerst een issue met het label `breaking change`, houd de oude vorm een tijd naast de nieuwe
als dat kan, zet een changelog-item in `changelog.d/` (zie `CONTRIBUTING.md`; bij de release komt het in
`CHANGELOG.md`) en noem het in de release-omschrijving ([Promoten](promoten.md)).
Verandert een toolschema of de `data_key`-afspraak bewust, pas dan de twee contracttests mee aan en zeg in het
changelog-item wat er anders is.

---

## Deep link naar de chat

`https://<omgeving>/chat#vraag=<tekst>` opent de chat met `<tekst>` in de invoer (#709). Zo verwijst de MCP-server in
`vervolg` naar de volledige app ([Bewijs en vervolg](mcp.md#bewijs-en-vervolg)); elke andere link kan het ook.

- De vraag staat in het fragment (`#`), niet in de query: een browser stuurt het fragment nooit naar een server of
  proxy, dus de vraag (vaak woorden uit wat de gebruiker elders vroeg) komt niet in een toegangslog; uvicorn en de
  ingress loggen het pad met de query (#103, #475). `?vraag=` leest de app niet.
- De app leest de parameter bij het laden, vóór het inloggen, en haalt hem uit het adres en de geschiedenis.
- De vraag wordt één regel platte tekst: stuur- en opmaaktekens (ook zero-width en bidi) en `<` `>` gaan eruit, en
  na 500 tekens wordt hij afgekapt.
- Hij wacht in `sessionStorage` van het tabblad. Zo overleeft hij het inloggen, ook via SRAM, dat na de callback
  op `/` terugkomt; de app gaat dan door naar `/chat`.
- De chat neemt de vraag één keer, begint een nieuw gesprek (het gesprek dat open stond gaat eerst naar de server,
  zoals bij "Nieuw gesprek") en zet hem in de invoer. Hij gaat pas naar het model als de gebruiker op versturen drukt.

---

## Infrastructuur

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/health` | Gezondheidscontrole — retourneert `{"status": "ok"}` |
| `GET` | `/ready` | Readiness-check (o.a. database); gebruikt door Kubernetes |
| `GET` | `/version`, `/api/version` | Versienummer: de release uit het chart (`APP_VERSION`, = de chartversie = de tag); zonder `APP_VERSION` (lokaal, `make dev`, MCP via stdio) een ontwikkellabel `<pyproject>+dev.<korte commit uit git>` (`2.8.0+dev.5e29298b`, zonder git of repo `2.8.0+dev`), dat nooit gelijk is aan een release (#1105; `core/appversie.py`). MCP `serverInfo.version` en het `app`-veld in het manifest van een rapport volgen hetzelfde label. De app-commit van het image, onder `catalogus` het catalogus-package `onderwijsbronnen` met de meegebouwde versie en `commit` (de volledige commit van deze repo waaruit het package komt, `null` als de build hem niet kent; het package staat sinds #885 in deze repo en bevat sinds #910 CBS, DUO, RIO en de andere bronnen; tot #910 stonden hier `onderwijsdata` en `riodata`), onder `manifest` ook de meegebouwde CBS-catalogus: `catalogusrevisie`, `consistent`, `aantal`, `laatste_succesvolle_controle` en `versheid`), onder `catalogus_digest` de digest (12 hex-tekens) van de catalogus die dit proces geladen heeft (`null` als die niet laadt), en onder `arbeidsmarkt` de dataversie van UWV en ROA (`bron`, `dataset`, `periode`), uit de statische catalogus van onderwijsbronnen en zonder download, en onder `mcp` of `/mcp` aan staat (`true` als `MCP_API_KEYS` gezet is; niets over de sleutels zelf, #941). `catalogusrevisie` zegt welk CBS-artefact is meegebouwd; `catalogus_digest` zegt welke catalogus dit proces geladen heeft, inclusief de bronvlaggen (SKDB, WOPI, financiën), en is dus gelijk aan `catalogus` in het manifest van een antwoord (#1029). Bewust zonder inloggen bereikbaar, voor de controle na een deploy (`SECURITY.md`, S20) |
| `GET` | `/info` | Naam en of OIDC aan staat |
| `GET` | `/api/config` | Publieke frontendconfiguratie (`routes/config.py`): `dashboards_enabled`, `feedback_enabled`, `max_message_chars` (maximum tekens per chatbericht, voor de invoerbalk), `max_chat_turns` (maximum vragen per gesprek), `max_history` (maximum berichten die het model ziet), `bewaartermijn_gesprekken_dagen` en `bewaartermijn_rapporten_dagen` (de termijnen van de opschoning, `null` als die een termijn weigert), `sessie_uren` en `sessie_max_uren`, en `bronnen`: per bron met een omgevingsregel of hij hier antwoord geeft (`tools/beschikbaarheid.py`, #956), voor de suggestievragen en het databronnenvenster |
| `GET` | `/api/bronstatus` | Welke bronnen nu niet live antwoorden (#1057). Openbaar, zonder token. Antwoord `{"niet_live": [...]}`: per bron `bron`, `naam`, `tekst` en `laatst_live`, een lege lijst als alles antwoordt. Nooit een URL of foutklasse. Meetregels en gedrag: [Operatie](operatie.md#bronstatus-in-de-app-1057) |
| `GET` | `/api/bronactualiteit` | Per bron (CBS, DUO, RIO, UWV, ROA, SKDB) en dataset hoe actueel de data is (#1266), voor de pagina `/bronnen`. Openbaar, zonder token. Antwoord `{"bronnen": [...], "uitleg": "…"}`: per bron `bron`, `naam`, `titel`, `url`, `bereikbaar` (`bereikbaar`, `niet bereikbaar` of `onbekend`, uit de bronstatus), `laatste_periode`, `laatste_wijziging`, `status` (`voorlopig`, `deels voorlopig`, `definitief` of `onbekend`), `frequentie`, `verwachte_volgende_editie` met `verwachte_volgende_editie_bron`, en `datasets`: per dataset dezelfde velden plus `id`, `titel`, `url`, `verwachte_volgende_editie_url`, `gecontroleerd_op` en `samenvatting`. UWV heeft ook `ouderdom` (`tekst`, `maanden`, `verouderd`; #1219), een bron die niet leest of niet antwoordt een `melding`. Een veld dat ontbreekt is `"onbekend"`, nooit `null` of leeg; een verwachte editie staat er alleen als de bron haar zelf noemt, met die bron. Uit de catalogus, zonder verzoek naar een bron. Waar elk veld vandaan komt: [Databronnen](databronnen.md#actualiteit-van-de-bronnen) |
| `GET` | `/api/catalog/counts` | Aantal datasets per bron dat de chat hier kan opvragen (`catalogus_aantallen` in `tools/catalog.py`): met een datatool (CBS, DUO, RIO), plus de bronnen met een eigen tool die hier antwoord geeft (zoals UWV, ROA, UNL of LCSK). Welke bronnen erin staan, verschilt dus per omgeving |
| `GET` | `/api/openapi.json` | Het OpenAPI-schema. Alleen lokaal, op development en op test; met `APP_ENV` `playground`, `production`, `staging-otc` of `production-otc` bestaat het niet (`SECURITY.md`, S23). Swagger UI (`/api/docs`) en ReDoc (`/redoc`) zijn er nergens: ze laadden hun scripts van `cdn.jsdelivr.net`, die de CSP blokkeert (#1161). Open het schema in een eigen viewer |

Welke paden de app-shell (`index.html`) geven en welke altijd JSON: [Routing](routing.md). Een onbekend pad onder `/api`,
of een gereserveerd pad als `/docs`, `/openapi.json` of `/status`, geeft 404 `{"detail": "Niet gevonden"}`.

---

## Authenticatie

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/auth/status` | Of authenticatie vereist is en of SRAM-login beschikbaar is (`{"required": …, "oidc_enabled": …}`) |
| `POST` | `/api/auth/login` | Inloggen met gebruikersnaam/wachtwoord. Retourneert een HMAC-ondertekend token. Rate-limited: 5 pogingen per minuut per IP. |
| `GET` | `/api/auth/oidc/login` | Start SRAM-login: redirect naar de OIDC-provider, met PKCE (S256) en een nonce |
| `GET` | `/api/auth/oidc/callback` | Callback van de provider; stuurt terug naar de app met het token in het fragment (`/#token=…`), nooit in de query. Controleert het `id_token` (handtekening, `iss`, `aud`, `exp`, `nonce`); bij een ongeldige login 400 zonder token (SECURITY.md S28) |
| `GET` | `/api/auth/session` | Of het token in `Authorization: Bearer …` nog geldt: 204 ja, 401 nee (ontbreekt, ongeldig, verlopen of ingetrokken). Altijd zonder body en zonder gebruikersgegevens; met en zonder OIDC. Zonder authenticatie 204; bij een databasestoring 500 |
| `GET` | `/api/auth/user` | Gebruikersinfo (naam, instelling) bij het token in `Authorization: Bearer …` — alleen als OIDC is ingesteld |
| `POST` | `/api/auth/refresh` | Vernieuwt een token vóór het verloopt, nooit voorbij `SESSION_MAX_HOURS` na inloggen — alleen als OIDC is ingesteld |
| `POST` | `/api/auth/logout` | Trekt het token in `Authorization: Bearer …` server-side in. Geeft 204, ook zonder of met een ongeldig token; bij een databasestoring 500 |

Zie [Configuratie → SURF SRAM-login](configuratie/index.md#surf-sram-login-oidc) voor de benodigde variabelen.

---

## Chat

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `WebSocket` | `/api/chat` (token als subprotocol: `["bearer", <token>]`) | WebSocket-sessie voor chat. Ondersteunt actions: `message`, `stop`, `ping`, `reset`, `settings`, `history`, `clarification_choice`, `plan_bevestigen`, `plan_aanpassen`, `generate_report`, `report_checklist`, `eigen_getal`. Een onbekende action of misvormd frame krijgt een `error`-event; de verbinding blijft open. `generate_dashboard` en `refresh_dashboard` zijn weg met de dashboardbouwer (#765), net als `POST /api/dashboard/refresh` |

- `reset` ("Nieuw gesprek") laat de server het lopende gesprek vergeten, inclusief geladen data; de server bevestigt met `reset_done`.
- `ping` is de hartslag van de frontend; de server antwoordt met `pong`.
- `settings` (`settings`: `model`, `functie`, `domein`, `instelling`) zet het profiel van de verbinding. Het `model` telt
  alleen binnen het aanbod van de gebruiker en, met login, alleen als het account "Geavanceerd" aan heeft
  (`/api/mijn-gegevens/geavanceerd`, bij elke vraag en elk rapport opnieuw gelezen); anders gebruikt de server `MODEL`
  (#755, #1269). Een sleutel `geavanceerd` in `settings` negeert de server.
- `message` (`content`, optioneel `geavanceerd`) stelt een vraag; `clarification_choice` (`choice`, optioneel
  `geavanceerd`) kiest een optie op een verduidelijkingskaart. `geavanceerd: true` telt alleen zonder login (de gedeelde
  `gast`): dan beslist die boolean of de vraag de plankaart kan krijgen (#1268). Met login leest de server de instelling
  bij elk verzoek uit de database en negeert hij het veld. Het zet alleen een extra kaart aan, nooit iets dat beschermt.
- `plan_bevestigen` (`id`, zonder login ook `geavanceerd`) is "Klopt, ga door" op de plankaart (#1268): de beurt gaat
  verder op dezelfde vraag, zonder nieuw gebruikersbericht. Code laadt precies de stappen van het plan met dat `id`, vóór
  de eerste modelronde, en weigert in die beurt elke andere laadaanroep met een melding aan het model. De antwoordcontrole
  na het antwoord is dezelfde. Kent de server het plan niet (meer), na herladen, een nieuwe verbinding of een nieuwe
  vraag, dan krijgt de client een `error` (`modelafhankelijk: false`) en loopt er niets. Telt als run: het token geldt
  opnieuw, de berichtlimiet telt mee, en tijdens een lopende vraag komt `busy`.
- `plan_aanpassen` (`id`) is "Pas aan": het plan vervalt zonder run en zonder antwoord. De frontend zet de vraag met de
  plankeuzes in het invoerveld; het model hoort bij de volgende vraag dat er niets geladen is.
- `history` (`messages`, optioneel `conv_id`) opent een opgeslagen gesprek: ook dat start een schone sessie. Die kent de tekst van dat gesprek en, met `conv_id`, de data keys uit de recepten van dat gesprek (#472) en het bewijs van de antwoorden in het frame (herkomst van de data, rekenbewijs, de bronregels van de geladen tabellen en de stappen achter de figuren, uit de tabel `beurtbewijs` en het geheugen, ADR-009). Met die bronregels krijgt een vervolgantwoord zonder toolaanroep dat de data van de vorige databeurt noemt zijn `bronnen` in `message_end`, ook als de server de data intussen niet meer heeft (#987); een gesprek van vóór #987 valt terug op wat de server nog weet. Het formaat van het frame blijft gelijk. De server meldt hoeveel met `history_data` (`data_keys`), zodat een rapport op die data kan zonder de vraag opnieuw te stellen.
- `generate_report` (`author`, optioneel `onderzoeksvraag`, `beurten` en `figuren`) maakt het rapport. `onderzoeksvraag` is de tekst die de gebruiker bevestigde (#750). `beurten` is de lijst nummers uit `report_checklist` die in het rapport horen (#908): de server controleert ze tegen het gesprek en rapporteert alleen over die beurten. Zonder `beurten`, of met alle, rust het rapport op het hele gesprek; een lege lijst, een onbekend nummer of iets dat geen lijst getallen is geeft een `error` (`modelafhankelijk: false`) en geen rapport. `figuren` is de lijst figuur-ids uit `report_checklist` die in het rapport komen (#993), hoogstens 4: de server maakt elke gekozen figuur opnieuw uit haar eigen vastgelegde stap (nooit uit figuur-JSON van de client) en een gekozen figuur trekt de beurten van haar data mee. Het rapport toont precies die figuren; zonder `figuren` of met een lege lijst heeft het geen figuren (besluit 18-11: het rapportmodel tekent zelf niets). Een onbekende id, iets dat geen lijst ids is, een dubbele id of meer dan 4 geeft een `error` en geen rapport. Een figuur die niet opnieuw lukt, valt weg met de regel "Deze figuur uit het gesprek kon niet opnieuw gemaakt worden." vooraan in `beantwoordt_niet`.
- `report_checklist` vraagt de beurten met data van het open gesprek (alleen lezen, geen model, geen berichtlimiet) en krijgt het event `report_checklist` terug, met `items`: per beurt `beurt` (het nummer), `vraag` (ingekort), `bronnen` (de bronregels van de data van die beurt), `bouwt_voort_op` (nummers van eerdere beurten waarvan de data ze gebruiken) en `figuren` (#993): de figuren uit het gesprek die op de data van die beurt rusten, als `{id, titel, beurten}` in de volgorde waarin ze ontstonden, met de titel van de figuur die de server maakte; `beurten` (#1045) zijn de nummers van alle beurten waarvan de figuur data gebruikt, haar eigen beurt inbegrepen: die trekt een gekozen figuur mee in het rapport. Een figuur staat bij de beurt waarin de data van haar `data_key` ontstond, ook als een latere beurt haar tekende ("maak hem horizontaal"). De lijst is leeg zonder data, en bij een gesprek zonder bewijs per beurt (van vóór #875); een gesprek van vóór #993 heeft geen figuren.
- `eigen_getal` (`id`, `getal`) legt een getal van de gebruiker naast het hoofdgetal van een antwoord, de knop "Wijkt af van je eigen cijfer?" (#1258, `agent/verschilverklaring.py`). `id` kiest het antwoord: de `id` uit `hoofdgetal` in zijn `message_end`. De server neemt alleen een hoofdgetal aan dat deze sessie zelf onder een antwoord zette (de laatste 20; na `reset` of `history` geen meer), en kent zelf ons getal, de teldefinitie en de andere definities; de client stuurt alleen `id` en het getal. `getal` (een tekst, of een heel getal) heeft alleen cijfers, hoogstens 12, met een punt of spatie (ook een harde spatie) alleen tussen groepen van drie cijfers: `475.460`, `475 460` en `1.234.567` mogen, `1.5`, `475.46`, een komma, een teken of tekst niet. Geen model en geen run: code antwoordt met `verschilverklaring` (het verschil, de redenen met hun grootte en de slotzin) of met `eigen_getal_fout` (`melding`), ook bij een onbekende `id`; tijdens een lopende vraag met `busy`. Het getal komt nooit in het log, alleen of het lukte. Het staat in de stap en het bewijs van de uitkomst als `eigen_getal`, invoer van de gebruiker (`invoer: gebruiker`) zonder citatie, en is nooit bewijs: de uitkomst gaat niet als historie naar het model, ook niet na `history` ([Anti-hallucinatie architectuur](anti-hallucination-architecture.md)).
- De WebSocket slaat zelf niets op. De frontend bewaart elk gesprek onder één ID via `PUT /api/conversations/{id}` (zie Persistentie).

**Events van de server** (JSON, veld `type`):

| Event | Betekenis |
|-------|-----------|
| `message_start`, `text_delta`, `message_end` | Een antwoord: begin, tekst die live binnenstroomt, en het eindresultaat met bronnen en acties. `message_end` met `aborted` of `partial` is een afgebroken of onvolledig antwoord. Rust het antwoord alleen op `get_maat`, dan heeft `message_end` `vaste_maat` (`maat`, `teldefinitie`, `vastgelegd_in`, `vastgelegd_op`; uit de toolstappen en het recept, nooit uit de modeltekst, #1242); zonder zo'n antwoord ontbreekt het veld. Geeft de beurt precies één hoofdgetal (een vaste maat met één rij, of een enkele selectie met één waarde; hetzelfde getal uit beide telt één keer), dan heeft `message_end` `hoofdgetal` (`id`, `waarde`; #1258): code haalt het uit de toolstappen, nooit uit de modeltekst, en de frontend zet er de knop "Wijkt af van je eigen cijfer?" onder (action `eigen_getal`). Onder een vast, leeg, geweigerd of ingehouden antwoord, en bij geen of meer dan één getal, ontbreekt het veld. `message_start` draagt `getalregel`: welke getallen de getalcontrole toetst; de frontend toont die pas na `message_end` (#1254). Een data-antwoord heeft `controles`: wat de antwoordcontrole deed, alleen tellingen uit code (#1260, zie [Voor auditors](anti-hallucination-architecture.md#voor-auditors)). Las het antwoord voorlopige CBS-cijfers, of noemt CBS voor een gelezen tabel een dag voor de volgende cijfers binnen 30 dagen, dan heeft `message_end` `actualiteit`: een lijst regels ("Let op: voorlopig cijfer: …", "Nieuwe editie verwacht op … (bron: …)"; #1266, [Databronnen](databronnen.md#actualiteit-van-de-bronnen)); anders ontbreekt het veld. Intern, zoals het hele protocol |
| `tool_start`, `tool_end`, `figure` | Een toolstap met zijn resultaat, en een grafiek die de stap tekende. `tool_start` draagt de argumenten van de aanroep (`input`); de frontend bewaart ze bij de stap, voor het bewijsbestand van het antwoord (#1244) |
| `message_cancel` | Het open antwoord vervalt (bij een verduidelijkingsvraag of de plankaart, of omdat een controle het intrekt; dan met `reden`). De tekst die al zichtbaar was, trekt de frontend zichtbaar in |
| `clarification` | Een verduidelijkingsvraag met opties; het antwoord gaat terug als action `clarification_choice` |
| `plan` | De plankaart (#1268), alleen met Geavanceerd, vóór het eerste laden van een vraag over twee of meer bronnen: `id`, `vraag` (de vraag met haar gekozen opties), `bronnen` (per bron `titel`, `dataset`, `versie` en `selectie`, een lijst regels in woorden), `sleutel` (de koppelsleutel in woorden, of `null` naast elkaar), `duur` (een grove tekst) en `tekst` (de kaart in één zin). Alles uit code, uit de argumenten van de laadstappen en de catalogus; geen tekst van het model. Het antwoord gaat terug als action `plan_bevestigen` of `plan_aanpassen` |
| `starter_questions` | Voorbeeldvragen bij een onderwerp uit de startkaarten ("Verken …") |
| `history_data` | Het aantal data keys dat bij een geopend gesprek terugkwam (zie `history`) |
| `report_checklist` | De beurten met data van het open gesprek, het antwoord op de action `report_checklist` (`items`, zie hierboven) |
| `verschilverklaring` | Het antwoord op de action `eigen_getal` (#1258): `content` is de uitkomst uit code (het eigen getal naast het onze, het verschil, de redenen en de slotzin), `id` het gekozen hoofdgetal en `stap` de stap erachter (`name`, `label`, `input`, `output`). De frontend toont het als een eigen bericht uit code, met de naam van die stap; het gaat niet als historie naar het model |
| `eigen_getal_fout` | Het eigen getal is niet aangenomen (`melding`: wat er mis is, zoals te veel cijfers of geen getal, of dat dit antwoord geen hoofdgetal meer heeft; `id`: het gekozen hoofdgetal, `null` als dat geen tekst was). De frontend toont de melding als korte waarschuwing |
| `report_generating`, `report_ready`, `report_error`, `report_cancelled` | Een rapport wordt gemaakt, is klaar, is geweigerd of mislukt (`report_error`, met `herstel: "rapport"` als opnieuw proberen past), of is geannuleerd |
| `toast` | Een korte melding (`message`, `level`) |
| `error` | Een fout in gewone woorden; `modelafhankelijk: false` als een ander model niets verandert |
| `busy` | De vorige vraag loopt nog |
| `run_slow` | De vraag duurt langer dan verwacht; de chat zegt dat onder de voortgang |
| `reset_done`, `pong` | Antwoord op `reset` en op `ping` |
| `system_message` | Een melding over de serverconfiguratie, zoals een ontbrekende API-sleutel |

**Een geweigerde handshake** sluit de server vóór het accepteren, dus de client krijgt geen sluitcode: een `Origin` die niet is toegestaan (`SECURITY.md`, S24) of bij het verbinden een token dat ontbreekt, ongeldig, verlopen of ingetrokken is, geeft een HTTP 403 op de handshake (een Python-client: `InvalidStatus`; een browser: een kale `1006`). Wacht in een eigen client dus niet op een sluitcode, maar lees de statuscode van de handshake.

**Sluitcodes van de verbinding** (ná het verbinden): `4001` het token is verlopen of ingetrokken, of ontbreekt, vóór een actie die een run start (`message`, `clarification_choice`, `plan_bevestigen`, `generate_report`; #786), dan zonder run. De andere acties, ook `ping`, toetsen het token niet opnieuw; `1013` er zijn te veel verbindingen open (de server stuurt eerst een `error`-event met de reden). Andere codes zijn gewone sluitingen of netwerkverlies.

---

## Instellingen & Dashboards

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/settings/config` | Beschikbare modellen en standaardmodel voor de ingelogde gebruiker. Met authenticatie aan alleen met een geldig token in `Authorization: Bearer …`, anders 401; zonder authenticatie voor `gast` |
| `GET` | `/api/instellingen` | Lijst van onderwijsinstellingen, optioneel gefilterd op `type` (query param, komma-gescheiden) |
| `GET` | `/api/dashboard/regio` | Dashboard-regiogegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/nationaal` | Dashboard-nationale gegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/rendement` | Dashboard-rendementsgegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/arbeidsmarktmatch` | Dashboard-arbeidsmarktmatch voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/financien` | Financiën van het bestuur van een instelling, uit DUO's verantwoording uit XBRL (`instelling` param, #935) |
| `GET` | `/api/dashboard/personeel` | Personeel (fte zonder GEZO) van een universiteit uit WOPI (`instelling` param, #936); alleen met `ENABLE_WO_PERSONEEL` |
| `GET` | `/api/dashboard/opleidingen` | Dashboard Opleidingen: per opleiding van een hbo- of wo-instelling de cijfers uit de Studiekeuzedatabase van LCSK (`instelling` param, #957) |

De `GET /api/dashboard/*`-eindpunten vragen met authenticatie aan een geldig token in `Authorization: Bearer …` (anders 401); zonder authenticatie zijn ze er voor `gast`. Zonder `ENABLE_DASHBOARDS=true` geven ze 403 `{"error": "Dashboards zijn niet beschikbaar"}` (#636). `financien`, `personeel` en `opleidingen` rusten op een bron met een omgevingsregel (`tools/beschikbaarheid.py`): waar die bron geen antwoord geeft (WOPI zonder `ENABLE_WO_PERSONEEL`, de financiën zonder bevestigde licentie, de Studiekeuzedatabase zonder `STUDIEKEUZEDATABASE_API_KEY`) geven ze 404 en laden ze niets. `opleidingen` geeft 503 als de export van LCSK niet laadt.

Er zijn geen andere dashboard-eindpunten (#954). `GET /api/dashboard/instroom` bestond tot versie 2.6.0 (#930) en geeft 410 met `error`: de cijfers van de eigen instelling staan in `regio`. Elk ander pad onder `/api/dashboard/` of `/api/dashboards` geeft 404 met in `error` de eindpunten hierboven. Geen van beide laadt data of vraagt een token.

---

## Persistentie

Met authenticatie aan zijn deze endpoints per ingelogde gebruiker afgeschermd. Zonder authenticatie horen alle gesprekken bij één gedeelde gebruiker (`gast`).

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/conversations` | Conversaties van de ingelogde gebruiker, nieuwste eerst, per pagina: `limit` (1–50, standaard 15); volgende pagina met `before_ts` en `before_id` van de laatste uit de vorige. Per rij alleen `id`, `title` en `timestamp`; met `q` alleen de treffers op titel of tekst |
| `GET` | `/api/conversations/{id}` | Eén conversatie met haar `messages`; 404 bij onbekend ID of een conversatie van een ander |
| `PUT` | `/api/conversations/{id}` | Maak of update een conversatie (`title`, `timestamp`, `messages`). De server kort `title` in tot 200 tekens en bewaart een titel met een BSN, e-mailadres of telefoonnummer als `Gesprek (persoonsgegevens weggelaten)`; een getal wordt tekst, een lijst, object of boolean wordt die generieke titel. 409 als `messages` niet begint met de vragen (`role: "user"`) die al bewaard zijn: een ander tabblad of apparaat schreef ertussen, en de bewaarde versie blijft staan; de frontend bewaart zijn versie dan als afsplitsing onder een nieuw ID (#760). Na een geslaagde `PUT` (dus niet na een 409) schrijft de server ook de bewijsrijen (`beurtbewijs`) van de antwoorden in `messages` waarvan de hash van hun `content` klaarstaat; een antwoord waarvan de client de tekst veranderde, krijgt er geen (ADR-009, #875) |
| `PATCH` | `/api/conversations/{id}` | Wijzig alleen de titel (`{"title": …}`), met dezelfde inkorting en maskering als bij `PUT`; 404 bij onbekend ID, 422 bij lege titel |
| `DELETE` | `/api/conversations/{id}` | Verwijder een conversatie |
| `POST` | `/api/conversations/{id}/antwoorden/{hash}/herhaal` | "Herhaal deze analyse" (#1240): haalt de CBS-tabellen achter een eigen antwoord opnieuw op en zet ze naast de stand van toen. `hash` is de sha256 (hex, 64 tekens) van de `content` van het antwoord, de sleutel van zijn bewijsrij (`beurtbewijs`); de tekst zelf gaat niet mee. Zonder modelaanroep en zonder modeltekst te vergelijken; het antwoord en de data in de app veranderen niet, en de herhaling wordt niet bewaard. Antwoord `{"bron": "cbs", "tabellen": [...], "overgeslagen": [...]}`: per tabel `dataset`, `titel`, `status` (`ongewijzigd`, `bijgewerkt`, `niet_te_vergelijken` als de app de stand van toen niet meer heeft, of `mislukt`), `samenvatting` (de zin onder het antwoord), `toen` en `nu` (`bijgewerkt_op`, `hash`: de inhoudshash) en `verschil` (`cellen`, `eerste` met `rij`, `kolom`, `toen` en `nu`, `rijen_erbij`, `rijen_weg`); bij `mislukt` een `melding` (bronfout of scopeweigering, zonder interne key; geen 5xx). `overgeslagen` noemt wat niet opnieuw gaat (een eigen berekening, DUO of RIO); zonder CBS-tabel is `tabellen` leeg met een `melding`. Telt als chatbericht: boven de berichtlimiet 429 met `Retry-After` en de melding van de chat, boven het tokenbudget 402 met de melding van het budget. 404 bij een onbekend antwoord en bij het antwoord van een ander, met dezelfde tekst; 422 bij een `hash` die geen sha256 is; 504 als de bron niet binnen 120 seconden antwoordt. In de app staat de knop alleen met de instelling "Geavanceerd" (#1269) |
| `GET` | `/api/workbooks` | Lijst van alle workbooks van de ingelogde gebruiker |
| `PUT` | `/api/workbooks/{id}` | Maak of update een workbook |
| `GET` | `/api/workbooks/{id}` | Eén workbook met zijn inhoud (de lijst heeft alleen wat een kaart toont, #633); 404 bij onbekend ID of een workbook van een ander. Openen telt als gebruik: de bewaartermijn begint opnieuw (#485) |
| `DELETE` | `/api/workbooks/{id}` | Verwijder een workbook |
| `POST` | `/api/workbooks/{id}/docx` | Een eigen rapport als bewerkbaar Word-document (#1038), gemaakt uit het bewaarde rapport met `templates/rapport.docx`. Het lichaam is leeg of `multipart/form-data` met alleen grafieken: `grafiek-<n>` (n = plek van de visualisatie, vanaf 0), elk een PNG van hooguit 2 MiB, hooguit 20. 404 bij onbekend ID of een workbook van een ander, 422 voor een workbook zonder rapport, 400/413 voor een ongeldige grafiek, 429 met `Retry-After` bij te veel verzoeken per minuut |

## Gegevens en feedback

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/data/csv` | De tabel achter een antwoord als CSV-bijlage (`key` als query param, met BOM voor Excel). Alleen voor een `key` waar een eigen gesprek een recept van heeft; na een herstart haalt de server de tabel opnieuw op. Een vreemde of verdwenen `key` geeft dezelfde 404; een bronfout 502. De header `X-Data-Herladen` meldt dat de cijfers kunnen afwijken van het eerdere antwoord (#269, #472). De knop ervoor staat in de app alleen met de instelling "Geavanceerd" (#1269) |
| `GET` | `/api/mijn-gegevens/export` | Alle gesprekken, werkboeken, feedback, datarecepten en het bewijs per antwoord (`beurtbewijs`: herkomst, rekenbewijs, sinds #987 de bronregels per data key als JSON (`bronnen`) en sinds #993 de stappen achter de figuren van het antwoord (`figuren`); sinds #983 zonder `controle` en sinds #1044 zonder `kaarten`) het tokengebruik per dag (`tokengebruik`: `dag` en `eenheden`, zonder de sleutel, #1074), het bewaarde SRAM-profiel (`oidc_gebruiker`: één rij met `gegevens` en `expires_at`, zonder de sleutel, of `[]`; #1209) en de instelling "Geavanceerd" (`geavanceerd`: één rij met `aan` en `gewijzigd`, zonder de sleutel, of `[]`; #1269) van de ingelogde gebruiker als JSON-bijlage, rij voor rij geschreven; `Cache-Control: no-store` (#645). Zonder login in de app (iedereen is dan `gast`) 404, zoals bij `DELETE`, want dan is er geen eigen account (#1118) |
| `GET` | `/api/mijn-gegevens/geavanceerd` | De instelling "Geavanceerd" van de ingelogde gebruiker: `{"geavanceerd": true}` of `false` (zonder bewaarde keuze `false`); alleen de eigen waarde, `Cache-Control: no-store`. Zonder login 404: dan houdt de browser de keuze zelf (#1269) |
| `PUT` | `/api/mijn-gegevens/geavanceerd` | Zet "Geavanceerd" aan of uit voor de ingelogde gebruiker, op elk apparaat. Body precies `{"geavanceerd": true}` of `{"geavanceerd": false}`, een ander veld of een andere waarde geeft 422; antwoord als bij `GET`. Zonder login 404 (#1269) |
| `DELETE` | `/api/mijn-gegevens` | Verwijdert al het werk van de ingelogde gebruiker in één transactie, ook het tokengebruik, het SRAM-profiel (`oidc_gebruikers`, #1209) en de instelling "Geavanceerd" (`geavanceerd`, #1269; `verwijderd` geeft het aantal per soort), en trekt alle tokens van het account in, ook die van een ander apparaat (#786). Body precies `{"bevestig": "verwijder"}`, anders 422; zonder authenticatie 404, want dan is er geen eigen account (#646) |
| `GET` | `/api/feedback/questions` | De vragenlijst voor feedback op een rapport of dashboard (`core/feedback.py`) |
| `GET` | `/api/feedback/given` | De werkboek-ID's waar de ingelogde gebruiker al feedback op gaf; leeg zonder login |
| `POST` | `/api/feedback` | Feedback op een eigen rapport of dashboard (#250); beperkt per gebruiker en werkboek, 429 met `Retry-After` |
| `POST` | `/api/feedback/algemeen` | Algemene feedback via de link Feedback (#600) |

De feedbackroutes geven 404 `Feedback staat uit` als `FEEDBACK_ENABLED` uit staat; `GET /api/config` meldt dat als `feedback_enabled`.

# API Referentie

De app draait op FastAPI en biedt een REST-API en WebSocket-endpoint voor communicatie met het frontend.

---

## Wat is stabiel

Niet elke interface is bedoeld om op te bouwen. De meegeleverde frontend draait altijd op dezelfde release als de server en
kent dus geen versieverschil; een andere client of een ander team heeft aan een kleiner, vast deel genoeg.

| Interface | Status | Waar je op kunt rekenen | Waar niet |
|---|---|---|---|
| `GET /health`, `/ready`, `/startup` | **stabiel** | Pad, methode en statuscode; `/health` geeft `{"status": "ok"}`. Kubernetes en de deploycontrole leunen erop. | Extra velden in de body. |
| `GET /version` | **stabiel** | De sleutels die bij `/version` hieronder staan; nieuwe sleutels komen erbij, bestaande verdwijnen niet. | Volgorde van sleutels. |
| MCP-server ([MCP](mcp.md)) | **stabiel** | Toolnamen, parameters, de envelope van `search_catalog` (`status`, `kandidaten`, `melding`, `vervolgstap`) en in elk resultaat de sleutels van `bewijs` en `vervolg` ([Bewijs en vervolg](mcp.md#bewijs-en-vervolg)). | De inhoud van `kandidaten` en de catalogus zelf: die volgt de bronnen. |
| Deep link `/chat#vraag=…` ([hieronder](#deep-link-naar-de-chat)) | **stabiel** | Pad en parameter: de vraag staat na het openen, ook na het inloggen, in de invoer van een nieuw gesprek en wordt niet vanzelf verstuurd. | Hoe de app de vraag schoont en de grens van 500 tekens. |
| Manifest bij een antwoord of rapport | **stabiel** | De bestaande sleutels (model, sampling, prompt-hash, catalogus, dataversie). | Nieuwe sleutels komen erbij zonder aankondiging. |
| Reproduceerbare snippet ([Reproduceerbare analyses](reproducibility.md)) | **stabiel in doel** | Hij laadt dezelfde bron met dezelfde filters en geeft dezelfde bewerkingen. | De exacte codetekst, en dat een bron later hetzelfde getal geeft (CBS herziet, DUO muteert cellen). |
| Alle overige `/api/*`-eindpunten en het WebSocket-protocol van `/api/chat` | **intern** | Alleen dat de frontend van dezelfde release werkt. | Alles; kan zonder aankondiging wijzigen. |
| Toolschema's voor het model (`tools/schemas.py`) en het `data_key`-formaat | **intern contract** | De keten `data_key` → filter → KPI/grafiek, bewaakt door `tests/test_tool_schema_contract.py` en `tests/test_tool_keten_contract.py`. | Het formaat van een `data_key`: behandel hem als ondoorzichtig, ook al ziet hij er leesbaar uit. |

**Wat telt als breaking change** in een stabiele interface: een pad, methode, toolnaam, parameter of sleutel die verdwijnt
of een andere naam krijgt; een betekenis die verandert; een optionele parameter die verplicht wordt. Een nieuwe tool, een
nieuwe optionele parameter of een nieuwe sleutel in een antwoord is dat niet.

**Wat je dan doet:** open eerst een issue met het label `breaking change`, houd de oude vorm een tijd naast de nieuwe
als dat kan, zet een regel in `CHANGELOG.md` en noem hem in de release-omschrijving ([Promoten](promoten.md)).
Verandert een toolschema of de `data_key`-afspraak bewust, pas dan de twee contracttests mee aan en zeg in het
changelog wat er anders is.

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
| `GET` | `/startup` | Startup-check; gebruikt door Kubernetes |
| `GET` | `/version` | Versienummer uit `pyproject.toml`, de app-commit van het image, onder `catalogus` per catalogus-package de meegebouwde versie en commit (CBS = package `onderwijsdata`, DUO en RIO = package `riodata`; bij `onderwijsdata` onder `manifest` ook de meegebouwde CBS-catalogus: `catalogusrevisie`, `consistent`, `aantal`, `laatste_succesvolle_controle` en `versheid`), en onder `arbeidsmarkt` de dataversie van UWV en ROA (`bron`, `dataset`, `periode`), uit de statische catalogus van riodata en zonder download. Bewust zonder inloggen bereikbaar, voor de controle na een deploy (`SECURITY.md`, S20) |
| `GET` | `/info` | Naam en of OIDC aan staat |
| `GET` | `/api/config` | Publieke frontendconfiguratie, o.a. `dashboards_enabled` en `max_message_chars` (maximum tekens per chatbericht, voor de invoerbalk) |
| `GET` | `/api/catalog/counts` | Aantal datasets per bron (CBS, DUO, RIO) uit de catalogus die de app doorzoekt |
| `GET` | `/api/docs`, `/redoc`, `/api/openapi.json` | API-documentatie (Swagger UI, ReDoc) en het OpenAPI-schema. Alleen lokaal, op development en op test; met `APP_ENV` `playground` of `production` bestaan ze niet (`SECURITY.md`, S23) |

---

## Authenticatie

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/auth/status` | Of authenticatie vereist is en of SRAM-login beschikbaar is (`{"required": …, "oidc_enabled": …}`) |
| `POST` | `/api/auth/login` | Inloggen met gebruikersnaam/wachtwoord. Retourneert een HMAC-ondertekend token. Rate-limited: 5 pogingen per minuut per IP. |
| `GET` | `/api/auth/oidc/login` | Start SRAM-login: redirect naar de OIDC-provider |
| `GET` | `/api/auth/oidc/callback` | Callback van de provider; stuurt terug naar de app met het token in het fragment (`/#token=…`), nooit in de query |
| `GET` | `/api/auth/session` | Of het token in `Authorization: Bearer …` nog geldt: 204 ja, 401 nee (ontbreekt, ongeldig, verlopen of ingetrokken). Altijd zonder body en zonder gebruikersgegevens; met en zonder OIDC. Zonder authenticatie 204; bij een databasestoring 500 |
| `GET` | `/api/auth/user` | Gebruikersinfo (naam, instelling) bij het token in `Authorization: Bearer …` — alleen als OIDC is ingesteld |
| `POST` | `/api/auth/refresh` | Vernieuwt een token vóór het verloopt, nooit voorbij `SESSION_MAX_HOURS` na inloggen — alleen als OIDC is ingesteld |
| `POST` | `/api/auth/logout` | Trekt het token in `Authorization: Bearer …` server-side in. Geeft 204, ook zonder of met een ongeldig token; bij een databasestoring 500 |

Zie [Configuratie → SURF SRAM-login](configuratie/index.md#surf-sram-login-oidc) voor de benodigde variabelen.

---

## Chat

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `WebSocket` | `/api/chat` (token als subprotocol: `["bearer", <token>]`) | WebSocket-sessie voor chat. Ondersteunt actions: `message`, `stop`, `ping`, `reset`, `settings`, `history`, `clarification_choice`, `generate_report`, `generate_dashboard`, `refresh_dashboard`. Een onbekende action of misvormd frame krijgt een `error`-event; de verbinding blijft open |
| `POST` | `/api/dashboard/refresh` | Ververs een bestaand dashboard via recipe/figure_recipes |

- `reset` ("Nieuw gesprek") laat de server het lopende gesprek vergeten, inclusief geladen data; de server bevestigt met `reset_done`.
- `ping` is de hartslag van de frontend; de server antwoordt met `pong`.
- `history` (`messages`, optioneel `conv_id`) opent een opgeslagen gesprek: ook dat start een schone sessie. Die kent de tekst van dat gesprek en, met `conv_id`, de data keys uit de recepten van dat gesprek (#472); de server meldt hoeveel met `history_data` (`data_keys`), zodat een rapport op die data kan zonder de vraag opnieuw te stellen.
- De WebSocket slaat zelf niets op. De frontend bewaart elk gesprek onder één ID via `PUT /api/conversations/{id}` (zie Persistentie).

**Events van de server** (JSON, veld `type`):

| Event | Betekenis |
|-------|-----------|
| `message_start`, `text_delta`, `message_end` | Een antwoord: begin, tekst die live binnenstroomt, en het eindresultaat met bronnen en acties. `message_end` met `aborted` of `partial` is een afgebroken of onvolledig antwoord |
| `message_cancel` | Het open antwoord vervalt (bij een verduidelijkingsvraag, of omdat een controle het intrekt; dan met `reden`). De tekst die al zichtbaar was, trekt de frontend zichtbaar in |
| `tool_start`, `tool_end`, `figure` | Een toolstap met zijn resultaat, en een grafiek die de stap tekende |
| `clarification` | Een verduidelijkingsvraag met opties; het antwoord gaat terug als action `clarification_choice` |
| `starter_questions` | Voorbeeldvragen bij een onderwerp uit de startkaarten ("Verken …") |
| `history_data` | Het aantal data keys dat bij een geopend gesprek terugkwam (zie `history`) |
| `dashboard_generating`, `dashboard_ready` | Een dashboard wordt gebouwd, en het klare dashboard (`spec`) |
| `report_generating`, `report_ready`, `report_error`, `report_cancelled` | Een rapport wordt gemaakt, is klaar, is geweigerd of mislukt (`report_error`, met `herstel: "rapport"` als opnieuw proberen past), of is geannuleerd |
| `toast` | Een korte melding (`message`, `level`) |
| `error` | Een fout in gewone woorden; `modelafhankelijk: false` als een ander model niets verandert |
| `busy` | De vorige vraag loopt nog |
| `run_slow` | De vraag duurt langer dan verwacht; de chat zegt dat onder de voortgang |
| `reset_done`, `pong` | Antwoord op `reset` en op `ping` |
| `system_message` | Een melding over de serverconfiguratie, zoals een ontbrekende API-sleutel |

**Sluitcodes van de verbinding:** `4001` token ontbreekt, is ongeldig of ingetrokken; `4003` de `Origin` is niet toegestaan (`SECURITY.md`, S24); `1013` er zijn te veel verbindingen open (de server stuurt eerst een `error`-event met de reden). Andere codes zijn gewone sluitingen of netwerkverlies.

---

## Instellingen & Dashboards

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/settings/config` | Beschikbare modellen en standaardmodel voor de ingelogde gebruiker. Met authenticatie aan alleen met een geldig token in `Authorization: Bearer …`, anders 401; zonder authenticatie voor `gast` |
| `GET` | `/api/instellingen` | Lijst van onderwijsinstellingen, optioneel gefilterd op `type` (query param, komma-gescheiden) |
| `GET` | `/api/dashboard/instroom` | Dashboard-instroomgegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/regio` | Dashboard-regiogegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/nationaal` | Dashboard-nationale gegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/rendement` | Dashboard-rendementsgegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/arbeidsmarktmatch` | Dashboard-arbeidsmarktmatch voor een instelling (`instelling` param) |

De vijf `GET /api/dashboard/*`-eindpunten vragen met authenticatie aan een geldig token in `Authorization: Bearer …` (anders 401); zonder authenticatie zijn ze er voor `gast`. Zonder `ENABLE_DASHBOARDS=true` geven ze 403 `{"error": "Dashboards zijn niet beschikbaar"}`, net als `POST /api/dashboard/refresh` (#636).

---

## Persistentie

Met authenticatie aan zijn deze endpoints per ingelogde gebruiker afgeschermd. Zonder authenticatie horen alle gesprekken bij één gedeelde gebruiker (`gast`).

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/conversations` | Conversaties van de ingelogde gebruiker, nieuwste eerst, per pagina: `limit` (1–50, standaard 15); volgende pagina met `before_ts` en `before_id` van de laatste uit de vorige. Per rij alleen `id`, `title` en `timestamp`; met `q` alleen de treffers op titel of tekst |
| `GET` | `/api/conversations/{id}` | Eén conversatie met haar `messages`; 404 bij onbekend ID of een conversatie van een ander |
| `PUT` | `/api/conversations/{id}` | Maak of update een conversatie (`title`, `timestamp`, `messages`). De server kort `title` in tot 200 tekens en bewaart een titel met een BSN, e-mailadres of telefoonnummer als `Gesprek (persoonsgegevens weggelaten)`; een getal wordt tekst, een lijst, object of boolean wordt die generieke titel |
| `PATCH` | `/api/conversations/{id}` | Wijzig alleen de titel (`{"title": …}`), met dezelfde inkorting en maskering als bij `PUT`; 404 bij onbekend ID, 422 bij lege titel |
| `DELETE` | `/api/conversations/{id}` | Verwijder een conversatie |
| `GET` | `/api/workbooks` | Lijst van alle workbooks van de ingelogde gebruiker |
| `PUT` | `/api/workbooks/{id}` | Maak of update een workbook |
| `GET` | `/api/workbooks/{id}` | Eén workbook met zijn inhoud (de lijst heeft alleen wat een kaart toont, #633); 404 bij onbekend ID of een workbook van een ander. Openen telt als gebruik: de bewaartermijn begint opnieuw (#485) |
| `DELETE` | `/api/workbooks/{id}` | Verwijder een workbook |

## Gegevens en feedback

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/data/csv` | De tabel achter een antwoord als CSV-bijlage (`key` als query param, met BOM voor Excel). Alleen voor een `key` waar een eigen gesprek een recept van heeft; na een herstart haalt de server de tabel opnieuw op. Een vreemde of verdwenen `key` geeft dezelfde 404; een bronfout 502. De header `X-Data-Herladen` meldt dat de cijfers kunnen afwijken van het eerdere antwoord (#269, #472) |
| `GET` | `/api/mijn-gegevens/export` | Alle gesprekken, werkboeken, feedback en datarecepten van de ingelogde gebruiker als JSON-bijlage, rij voor rij geschreven; `Cache-Control: no-store` (#645) |
| `DELETE` | `/api/mijn-gegevens` | Verwijdert al het werk van de ingelogde gebruiker in één transactie en trekt het token in. Body precies `{"bevestig": "verwijder"}`, anders 422; zonder authenticatie 404, want dan is er geen eigen account (#646) |
| `GET` | `/api/answer-feedback` | De 👍/👎 op de antwoorden van een gesprek (`conversation_id`) |
| `POST` | `/api/answer-feedback` | 👍/👎 op een antwoord (`conversation_id`, `message_index`, `oordeel` `up` of `down`, `toelichting`); de trace komt uit het eigen opgeslagen gesprek (#248) |
| `GET` | `/api/feedback/questions` | De vragenlijst voor feedback op een rapport of dashboard (`core/feedback.py`) |
| `GET` | `/api/feedback/given` | De werkboek-ID's waar de ingelogde gebruiker al feedback op gaf; leeg zonder login |
| `POST` | `/api/feedback` | Feedback op een eigen rapport of dashboard (#250); beperkt per gebruiker en werkboek, 429 met `Retry-After` |
| `POST` | `/api/feedback/algemeen` | Algemene feedback via de link Feedback (#600) |

De feedbackroutes geven 404 `Feedback staat uit` als `FEEDBACK_ENABLED` uit staat; `GET /api/config` meldt dat als `feedback_enabled`.

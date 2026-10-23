# API Referentie

De app draait op FastAPI en biedt een REST-API en WebSocket-endpoint voor communicatie met het frontend.

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
| `WebSocket` | `/api/chat` (token als subprotocol: `["bearer", <token>]`) | WebSocket-sessie voor chat. Ondersteunt actions: `message`, `stop`, `reset`, `settings`, `history`, `clarification_choice`, `generate_report`, `generate_dashboard`, `refresh_dashboard` |
| `POST` | `/api/dashboard/refresh` | Ververs een bestaand dashboard via recipe/figure_recipes |

- `reset` ("Nieuw gesprek") laat de server het lopende gesprek vergeten, inclusief geladen data; de server bevestigt met `reset_done`.
- `history` opent een opgeslagen gesprek: ook dat start een schone sessie, die alleen de tekst van dat gesprek kent.
- De WebSocket slaat zelf niets op. De frontend bewaart elk gesprek onder één ID via `PUT /api/conversations/{id}` (zie Persistentie).

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

De vijf `GET /api/dashboard/*`-eindpunten vragen met authenticatie aan een geldig token in `Authorization: Bearer …` (anders 401); zonder authenticatie zijn ze er voor `gast`. Met `ENABLE_DASHBOARDS=false` geven ze 403 `{"error": "Dashboards zijn niet beschikbaar"}`, net als `POST /api/dashboard/refresh` (#636).

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
| `DELETE` | `/api/workbooks/{id}` | Verwijder een workbook |

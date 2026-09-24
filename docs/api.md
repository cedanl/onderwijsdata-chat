# API Referentie

De app draait op FastAPI en biedt een REST-API en WebSocket-endpoint voor communicatie met het frontend.

---

## Infrastructuur

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/health` | Gezondheidscontrole — retourneert `{"status": "ok"}` |
| `GET` | `/ready` | Readiness-check (o.a. database); gebruikt door Kubernetes |
| `GET` | `/startup` | Startup-check; gebruikt door Kubernetes |
| `GET` | `/version` | Versienummer uit `pyproject.toml` |
| `GET` | `/info` | Naam, of OIDC aan staat, databasetype (PostgreSQL/SQLite) en omgeving |
| `GET` | `/api/config` | Publieke frontendconfiguratie, o.a. `dashboards_enabled` |
| `GET` | `/api/catalog/counts` | Aantal datasets per bron (CBS, DUO, RIO) uit de catalogus die de app doorzoekt |

---

## Authenticatie

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/auth/status` | Of authenticatie vereist is en of SRAM-login beschikbaar is (`{"required": …, "oidc_enabled": …}`) |
| `POST` | `/api/auth/login` | Inloggen met gebruikersnaam/wachtwoord. Retourneert een HMAC-ondertekend token. Rate-limited: 5 pogingen per minuut per IP. |
| `GET` | `/api/auth/oidc/login` | Start SRAM-login: redirect naar de OIDC-provider |
| `GET` | `/api/auth/oidc/callback` | Callback van de provider; zet het token en stuurt terug naar de app |
| `GET` | `/api/auth/user` | Gebruikersinfo (naam, instelling) bij een token — alleen als OIDC is ingesteld |
| `POST` | `/api/auth/refresh` | Vernieuwt een token vóór het verloopt — alleen als OIDC is ingesteld |

Zie [Configuratie → SURF SRAM-login](configuratie/index.md#surf-sram-login-oidc) voor de benodigde variabelen.

---

## Chat

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `WebSocket` | `/api/chat?token=<token>` | WebSocket-sessie voor chat. Ondersteunt actions: `message`, `stop`, `reset`, `settings`, `history`, `clarification_choice`, `generate_report`, `generate_dashboard`, `refresh_dashboard` |
| `POST` | `/api/dashboard/refresh` | Ververs een bestaand dashboard via recipe/figure_recipes |

- `reset` ("Nieuw gesprek") laat de server het lopende gesprek vergeten, inclusief geladen data; de server bevestigt met `reset_done`.
- `history` opent een opgeslagen gesprek: ook dat start een schone sessie, die alleen de tekst van dat gesprek kent.
- De WebSocket slaat zelf niets op. De frontend bewaart elk gesprek onder één ID via `PUT /api/conversations/{id}` (zie Persistentie).

---

## Instellingen & Dashboards

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/settings/config` | Beschikbare modellen en standaardmodel voor de (optioneel ingelogde) gebruiker |
| `GET` | `/api/instellingen` | Lijst van onderwijsinstellingen, optioneel gefilterd op `type` (query param, komma-gescheiden) |
| `GET` | `/api/dashboard/instroom` | Dashboard-instroomgegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/regio` | Dashboard-regiogegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/nationaal` | Dashboard-nationale gegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/rendement` | Dashboard-rendementsgegevens voor een instelling (`instelling` param) |
| `GET` | `/api/dashboard/arbeidsmarktmatch` | Dashboard-arbeidsmarktmatch voor een instelling (`instelling` param) |

---

## Persistentie

Met authenticatie aan zijn deze endpoints per ingelogde gebruiker afgeschermd. Zonder authenticatie horen alle gesprekken bij één gedeelde gebruiker (`gast`).

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/conversations` | Lijst van alle conversaties van de ingelogde gebruiker |
| `PUT` | `/api/conversations/{id}` | Maak of update een conversatie (`title`, `timestamp`, `messages`) |
| `PATCH` | `/api/conversations/{id}` | Wijzig alleen de titel (`{"title": …}`); 404 bij onbekend ID, 422 bij lege titel |
| `DELETE` | `/api/conversations/{id}` | Verwijder een conversatie |
| `GET` | `/api/workbooks` | Lijst van alle workbooks van de ingelogde gebruiker |
| `PUT` | `/api/workbooks/{id}` | Maak of update een workbook |
| `DELETE` | `/api/workbooks/{id}` | Verwijder een workbook |

# API Referentie

De app draait op FastAPI en biedt een REST-API en WebSocket-endpoint voor communicatie met het frontend.

---

## Infrastructuur

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/health` | Gezondheidscontrole — retourneert `{"status": "ok"}` |
| `GET` | `/version` | Versienummer uit `pyproject.toml` |

---

## Authenticatie

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/auth/status` | Geeft aan of authenticatie vereist is (`{"required": true/false}`) |
| `POST` | `/api/auth/login` | Inloggen met gebruikersnaam/wachtwoord. Retourneert JWT-token. Rate-limited: 5 pogingen/minuut. |

---

## Chat

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `WebSocket` | `/api/chat?token=<jwt>` | WebSocket-sessie voor chat. Ondersteunt actions: `message`, `stop`, `settings`, `history`, `clarification_choice`, `generate_dashboard`, `refresh_dashboard` |
| `POST` | `/api/dashboard/refresh` | Ververs een bestaand dashboard via recipe/figure_recipes |

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

Vereist authenticatie (`CHAT_USERS` + `CHAT_SECRET`).

| Methode | Pad | Beschrijving |
|---------|-----|--------------|
| `GET` | `/api/conversations` | Lijst van alle conversaties van de ingelogde gebruiker |
| `PUT` | `/api/conversations/{id}` | Maak of update een conversatie |
| `DELETE` | `/api/conversations/{id}` | Verwijder een conversatie |
| `GET` | `/api/workbooks` | Lijst van alle workbooks van de ingelogde gebruiker |
| `PUT` | `/api/workbooks/{id}` | Maak of update een workbook |
| `DELETE` | `/api/workbooks/{id}` | Verwijder een workbook |

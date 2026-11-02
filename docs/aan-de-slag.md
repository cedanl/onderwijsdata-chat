# Aan de slag

## Vereisten

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- Python 3.11 of hoger (wordt automatisch beheerd door uv)
- Een API key voor een ondersteund taalmodel — zie [Providers & modellen](configuratie/providers.md)
- Node.js **24 of hoger** (zie `.nvmrc`) — alleen nodig voor frontend-ontwikkeling en de frontendtests; op Node 20 falen de tests met een cryptische `undici`-importfout

### uv installeren

=== "Linux / macOS"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

---

## Installatie

```bash
# 1. Clone de repository
git clone https://github.com/cedanl/onderwijsdata-chat.git
cd onderwijsdata-chat

# 2. Kopieer de voorbeeldconfiguratie
cp .env.example .env

# 3. Vul je model en API key in .env in (zie Configuratie)

# 4. Installeer dependencies
uv sync
```

---

## Starten

```bash
make dev
```

De app herstart automatisch bij bestandswijzigingen. Open vervolgens je browser op de juiste URL (zie hieronder).

### Bereikbaarheid vanuit de browser

`make dev` start de frontend (Vite) op poort 5173 (`FRONTEND_PORT`) en de backend op 8000 (`BACKEND_PORT`); de
frontend stuurt `/api` door naar de backend. Open de frontend:

=== "Lokaal of met doorgestuurde poorten"
    ```
    http://localhost:5173
    ```

=== "Container zonder doorgestuurde poorten"
    Komen de poorten van de container niet op de host (bijvoorbeeld met devcontainer-cli zonder VS Code), gebruik dan
    het IP van de container:
    ```bash
    make url   # print de juiste URL, bijv. http://172.17.0.2:5173
    ```

---

## Chatgeschiedenis inschakelen (optioneel)

Standaard werkt de app lokaal zonder login. Gesprekken worden dan wel bewaard, maar allemaal onder één gedeelde gebruiker
(`gast`). Een eigen geschiedenis per gebruiker krijg je met een login. Voeg daarvoor twee variabelen toe aan `.env`:

```dotenv
CHAT_USERS=gebruikersnaam:wachtwoord
CHAT_SECRET=<willekeurige lange string>
```

`CHAT_SECRET` is het HMAC-secret voor sessiebeheer. Met een login is het verplicht: zonder `CHAT_SECRET` start de app
niet en noemt de melding hoe je een waarde maakt (`python -c "import secrets; print(secrets.token_hex(32))"`).

Meerdere gebruikers zijn mogelijk als kommalijst: `CHAT_USERS=alice:ww1,bob:ww2`.

Na een herstart verschijnt het loginscherm en wordt elk gesprek automatisch opgeslagen — lokaal in het SQLite-bestand `onderwijsdata.db`, of in PostgreSQL als `POSTGRES_URI` is ingesteld. Eerdere gesprekken zijn terug te vinden in de linkerzijbalk, of met **Ctrl+K** (⌘K op een Mac) of de zoekknop in de kop: dat zoekt in één keer in je gesprekken (titel en tekst) en rapporten (titel).

!!! tip "Uitschakelen"
    Verwijder `CHAT_USERS` uit `.env` om terug te gaan naar de modus zonder login, met de gedeelde gebruiker `gast`.

---

## Je eerste vraag

Na het opstarten verschijnt het chatvenster. Probeer bijvoorbeeld:

> *"Hoeveel studenten zijn er in 2023 ingeschreven in het WO?"*

> *"Vergelijk mbo-diplomering in de G4-steden over de afgelopen 5 jaar en maak een grafiek."*

> *"Welke DUO-datasets zijn beschikbaar over studentprognoses?"*

De assistent zoekt automatisch de juiste datasets op, haalt de data op en presenteert resultaten direct in de chat. Bij elke tool-aanroep wordt een reproduceerbaar Python-snippet getoond.

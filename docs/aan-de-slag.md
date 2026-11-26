---
icon: lucide/rocket
---

# Installatie voor ontwikkelaars

## Vereisten

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- Python 3.11 of hoger (uv beheert dit; `.python-version` pint 3.14)
- Een API key voor een ondersteund taalmodel — zie [Providers & modellen](configuratie/providers.md)
- Node.js **24 of hoger** (`.nvmrc` en de CI gebruiken Node 26) — alleen nodig voor frontend-ontwikkeling en de frontendtests; op Node 20 falen de tests met een cryptische `undici`-importfout

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

De assistent zoekt automatisch de juiste datasets op, haalt de data op en presenteert resultaten direct in de chat. Met
de instelling **Geavanceerd** (hieronder) staat bij elke tool-aanroep ook een reproduceerbaar Python-snippet.

---

## Instelling "Geavanceerd"

In **Instellingen** (je naam rechtsboven) staat de schakelaar **Geavanceerd**, standaard uit. Hij is voor wie de
analyse achter een antwoord zelf wil zien en bijsturen. Aan zet hij erbij (#1269):

- de Python-code per stap in de kaart "Redenering", en in de gespreksexport de keuze "Code per stap";
- de technische key onder "Technische details" bij een getal met herkomst;
- de downloads "Download data als CSV" en "Download cijfers als CSV", met "Vraag opnieuw stellen" als een download
  mislukt;
- **Herhaal deze analyse** onder een antwoord met een CBS-tabel: de app haalt die tabellen opnieuw op en zet de stand
  van nu naast die van toen, alleen getallen en bronversie (#1240, zie
  [Reproduceerbare analyses](reproducibility.md#is-het-dezelfde-data-peildag-bestandsversie-en-hash));
- de modelkiezer en "Opnieuw met <ander model>" na een fout. Uit gaat elke vraag met het standaardmodel (`MODEL`); de
  server houdt zich daar zelf ook aan.

Geavanceerd zet alleen iets erbij. De controles en waarschuwingen bij een antwoord, de herkomst van een getal in
woorden, de bronnen en de CSV onder een grafiek staan er altijd, ook als hij uit staat (zie
[Kwaliteit en veiligheid](kwaliteit-en-veiligheid.md#geavanceerd-alleen-erbij-nooit-minder-bescherming)).

Bij de eerste keer inloggen vraagt de welkomstdialoog: *"Wil je de code en de data achter een antwoord zien en zelf
bijsturen?"*, met **Nee** als standaard; **Ja** zet Geavanceerd aan. Met een login staat je keuze bij je account op de
server, dus op elk apparaat dezelfde. Zonder login (de gedeelde gebruiker `gast`) bewaart alleen deze browser hem.

Een beheerder kan de instelling voor een pilotgroep aanzetten met `GEAVANCEERD_PILOT` (zie
[Configuratie](configuratie/index.md)): bij de eerste login van zo'n account staat hij dan aan. Daarna beslis je zelf; zet
je hem uit, dan blijft hij uit. Nooit bepaalt je rol, instelling of functie of hij aan staat.

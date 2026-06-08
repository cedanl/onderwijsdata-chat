# Aan de slag

## Vereisten

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- Python 3.11 of hoger (wordt automatisch beheerd door uv)
- Een API key voor een ondersteund taalmodel — zie [Providers & modellen](configuratie/providers.md)

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

=== "VS Code devcontainer"
    Poorten worden automatisch doorgestuurd — open:
    ```
    http://localhost:8000
    ```

=== "devcontainer-cli (plain Docker)"
    `forwardPorts` in `devcontainer.json` werkt niet zonder VS Code. Gebruik het container-bridge-IP:
    ```bash
    make url   # print de juiste URL, bijv. http://172.17.0.2:8000
    ```

=== "Lokaal (geen container)"
    ```
    http://localhost:8000
    ```

---

## Chatgeschiedenis inschakelen (optioneel)

Standaard werkt de app zonder login en zonder opgeslagen gespreksgeschiedenis. Schakel het in door twee variabelen toe te voegen aan `.env`:

```bash
# 1. Genereer een secret (eenmalig)
chainlit create-secret
```

Voeg de output toe aan `.env`:

```dotenv
CHAINLIT_AUTH_SECRET="<gegenereerde waarde>"
CHAT_USERS=gebruikersnaam:wachtwoord
```

Meerdere gebruikers zijn mogelijk als kommalijst: `CHAT_USERS=alice:ww1,bob:ww2`.

Na een herstart verschijnt het loginscherm en wordt elk gesprek automatisch opgeslagen in `chat_history.db`. Eerdere gesprekken zijn terug te vinden in de linkerzijbalk.

!!! tip "Uitschakelen"
    Commentarieer `CHAINLIT_AUTH_SECRET` uit in `.env` om terug te gaan naar de anonieme modus.

---

## Je eerste vraag

Na het opstarten verschijnt het chatvenster. Probeer bijvoorbeeld:

> *"Hoeveel studenten zijn er in 2023 ingeschreven in het WO?"*

> *"Vergelijk mbo-diplomering in de G4-steden over de afgelopen 5 jaar en maak een grafiek."*

> *"Welke DUO-datasets zijn beschikbaar over studentprognoses?"*

De assistent zoekt automatisch de juiste datasets op, haalt de data op en presenteert resultaten direct in de chat.

---

## Eigen bestanden uploaden

Klik op de **paperclip** in het invoerveld om een **xlsx- of csv-bestand** te uploaden. Na het uploaden toont de assistent het schema en kun je direct vragen stellen:

> *"Geef een samenvatting van dit bestand."*

> *"Maak een grafiek van de verdeling per collegejaar."*

> *"Vergelijk deze upload met de CBS-data over hetzelfde onderwerp."*

Bij bestanden met meerdere sheets worden alle sheets afzonderlijk ingelezen en zijn ze elk beschikbaar als eigen databron.

!!! note "Resume"
    Uploads worden automatisch bewaard bij gesprekken met ingelogde gebruikers (zie [Chatgeschiedenis inschakelen](#chatgeschiedenis-inschakelen-optioneel)). Je hoeft het bestand niet opnieuw te uploaden als je een gesprek hervat.

---

## Reproduceerbare code downloaden

Na elk antwoord verschijnen drie knoppen: **📥 HTML**, **📄 PDF** en **📦 Reproduceerbare code**.

De zip bevat:

| Bestand | Inhoud |
|---------|--------|
| `analyse.py` | Uitvoerbaar Python-script — één blok per vraag |
| `analyse.ipynb` | Notebook-versie met vraag/antwoord en codecellen |
| `requirements.txt` | Alleen gebruikte packages, versies gepind |
| `LEESMIJ.md` | Installatie-instructies (uv en pip) |

**Voor CBS/DUO/RIO analyses** roept het script de tools rechtstreeks aan — de `tools/`-map uit de repository is vereist.

**Voor analyses op geüploade bestanden** bevat `analyse.py` zelfstandige `pandas`/`plotly`-code die filters en aggregaties reconstrueert. Alleen het originele bestand is nodig, niet de `tools/`-map.

```bash
# Installeren en uitvoeren (uv)
uv venv
uv pip install -r requirements.txt
python analyse.py
```

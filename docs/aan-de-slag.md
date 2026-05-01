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

## Je eerste vraag

Na het opstarten verschijnt het chatvenster. Probeer bijvoorbeeld:

> *"Hoeveel studenten zijn er in 2023 ingeschreven in het WO?"*

> *"Vergelijk mbo-diplomering in de G4-steden over de afgelopen 5 jaar en maak een grafiek."*

> *"Welke DUO-datasets zijn beschikbaar over studentprognoses?"*

De assistent zoekt automatisch de juiste datasets op, haalt de data op en presenteert resultaten direct in de chat.

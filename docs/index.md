# Onderwijsdata Chat

**Stel vragen over open Nederlandse onderwijsdata via een AI-assistent.**

<video src="assets/demo.mp4" controls width="100%"></video>

De assistent heeft directe toegang tot CBS, RIO en DUO, kan grafieken en choropleth-kaarten genereren, en toont reproduceerbare Python-code bij elke tool-aanroep — zonder dat je zelf hoeft te programmeren of data te downloaden.

---

## Wat kan je ermee?

- **Vragen in gewone taal** — "Hoeveel studenten zijn er ingeschreven in de WO in 2023?" of "Vergelijk mbo-diplomering tussen regio's"
- **Interactieve grafieken en kaarten** — de assistent maakt automatisch Plotly-visualisaties en choropleth-kaarten op basis van je vraag
- **Dashboards** — laat de assistent een interactief dashboard genereren op basis van je data, bekijk en beheer ze in de dashboard-galerij
- **Reproduceerbare code** — bij elke tool-aanroep wordt een Python-snippet getoond waarmee je de analyse lokaal kunt herhalen
- **Sandbox-analyse** — voer pandas/numpy-code uit op opgehaalde data via de ingebouwde `run_analysis`-tool
- **Meerdere databronnen combineren** — CBS-statistieken, RIO-registers en DUO-datasets in één gesprek

## Databronnen

| Bron | Inhoud | Catalogus |
|------|--------|-----------|
| **CBS** | 68 datasets met onderwijsstatistieken | [cedanl.github.io/cbs-onderwijsdata](https://cedanl.github.io/cbs-onderwijsdata/) |
| **RIO** | Register van onderwijsinstellingen en opleidingen (14 resources) | [cedanl.github.io/rio-onderwijsdata](https://cedanl.github.io/rio-onderwijsdata/) |
| **DUO** | 57 open datasets: prognoses, diplomering, instroom, adressen | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |

## Snel aan de slag

```bash
cp .env.example .env
# Vul je API key in .env in
uv sync
make dev
```

Zie [Aan de slag](aan-de-slag.md) voor gedetailleerde installatie-instructies en [Configuratie](configuratie/index.md) voor alle instellingen.

---

Dit project is onderdeel van de [CEDA](https://github.com/cedanl) organisatie.

# Onderwijsdata Chat

**Stel vragen over open Nederlandse onderwijsdata via een AI-assistent.**

De assistent heeft directe toegang tot CBS, RIO en DUO en kan grafieken genereren en een downloadbaar HTML-rapport produceren — zonder dat je zelf hoeft te programmeren of data te downloaden.

---

## Wat kan je ermee?

- **Vragen in gewone taal** — "Hoeveel studenten zijn er ingeschreven in de WO in 2023?" of "Vergelijk mbo-diplomering tussen regio's"
- **Interactieve grafieken** — de assistent maakt automatisch Plotly-visualisaties op basis van je vraag
- **HTML-rapport downloaden** — alle analyses en grafieken van een sessie in één bestand
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

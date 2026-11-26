---
icon: lucide/house
---

# Onderwijsdata Chat

**Stel vragen over open Nederlandse onderwijsdata via een AI-assistent.**

<video src="assets/demo.mp4" controls width="100%"></video>

De assistent heeft directe toegang tot CBS, RIO en DUO, kan grafieken en choropleth-kaarten genereren, en toont reproduceerbare Python-code bij elke tool-aanroep — zonder dat je zelf hoeft te programmeren of data te downloaden.

---

## Waar begin je?

| Je wilt | Ga naar |
|---------|---------|
| Weten wat dit is en voor wie | [Over Onderwijsdata Chat](product/over.md) |
| Zien wat je ermee kunt | [Wat kun je ermee](product/mogelijkheden.md) en [Voorbeeldvragen](product/voorbeelden.md) |
| Zelf beginnen | [Aan de slag als gebruiker](product/aan-de-slag.md) |
| Weten waar de cijfers vandaan komen | [Databronnen begrijpen](product/databronnen.md) |
| Weten of een antwoord klopt | [Een antwoord lezen en controleren](product/betrouwbaarheid.md) |
| Weten wat er met je gegevens gebeurt | [Privacy in gewone taal](product/privacy.md) |
| Een vraag of een probleem hebben | [Veelgestelde vragen](product/faq.md) en [Problemen oplossen](product/problemen-oplossen.md) |
| De app zelf draaien of koppelen | [Installatie voor ontwikkelaars](aan-de-slag.md), [API](api.md) en [MCP-server](mcp.md) |
| De app beheren | [Configuratie](configuratie/index.md), [Operatie & runbook](operatie.md) en [Hosting](hosting.md) |

De menubalk volgt dezelfde indeling: **Product & gebruik** en **Techniek & beheer**.

## Wat kan je ermee?

- **Vragen in gewone taal** — "Hoeveel studenten zijn er ingeschreven in de WO in 2023?" of "Vergelijk mbo-diplomering tussen regio's"
- **Interactieve grafieken en kaarten** — de assistent maakt automatisch Plotly-visualisaties en choropleth-kaarten op basis van je vraag
- **Dashboards** — vaste dashboards per instelling, waar de omgeving ze aanzet: drie (Mijn instelling, Arbeidsmarkt, Landelijk), en waar de Studiekeuzedatabase aan staat vier, met Opleidingen
- **Reproduceerbare code** — met de instelling "Geavanceerd" staat bij elke tool-aanroep een Python-snippet waarmee je de analyse lokaal kunt herhalen
- **Sandbox-analyse** — voer pandas/numpy-code uit op opgehaalde data via de ingebouwde `run_analysis`-tool
- **Meerdere databronnen combineren** — CBS-statistieken, RIO-registers en DUO-datasets in één gesprek

## Databronnen

| Bron | Inhoud | Catalogus |
|------|--------|-----------|
| **CBS** | 132 datasets met onderwijsstatistieken over mbo, hbo en wo; negen daarvan gaan over het vo, alleen als vo-context voor vervolgonderwijs, en twee over vacatures: 83599NED (openstaand, per provincie en bedrijfstak, per kwartaal; in de chat via `get_vacatures`, in de dashboards sinds #1225) en 85081NED (ontstaan, per beroep, landelijk, per jaar; via `get_ontstane_vacatures`) | [catalogus/cbs](https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/) |
| **RIO** | Register van onderwijsinstellingen en opleidingen, met sectorfilter op mbo/hbo/wo (8 resources) | [catalogus/rio](https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/) |
| **DUO** | 15 open datasets over mbo, hbo en wo: prognoses, diplomering, instroom, adressen; één daarvan (`voprognoses`) is alleen vo-context voor vervolgonderwijs | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |
| **ROA** | Arbeidsmarkt-prognoses per opleidingsniveau en -sector (AIS 2030, de nieuwste editie in de catalogus, met de schoolverlatersinformatie SIS); in de chat via `get_roa_benchmark` en in de dashboards | — |
| **UWV** | Open match vacatures (momentopname mei 2023, UWV maakt de reeks niet meer); in de chat alleen als archief via `get_uwv_vacatures`, de actuele vacatures komen van CBS | — |

## Snel aan de slag

```bash
cp .env.example .env
# Vul je API key in .env in
uv sync
make dev
```

Zie [Installatie voor ontwikkelaars](aan-de-slag.md) voor gedetailleerde installatie-instructies en [Configuratie](configuratie/index.md) voor alle instellingen.

---

Dit project is onderdeel van de [CEDA](https://github.com/cedanl) organisatie.

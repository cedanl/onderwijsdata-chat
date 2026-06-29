const DC_MESSAGES_KEY = 'edudata_dc_messages'
const DC_FIGURES_KEY = 'edudata_dc_figures'

const SEED_MESSAGES = [
  {
    id: 1,
    role: 'user',
    content: 'Hoeveel gediplomeerden levert Hogeschool Utrecht per jaar op ten opzichte van andere instellingen in Utrecht?',
    done: true,
  },
  {
    id: 2,
    role: 'assistant',
    content: `Hier is een overzicht van het aantal gediplomeerden bij Hogeschool Utrecht en vergelijkbare instellingen in de regio Utrecht over de afgelopen jaren.

## Gediplomeerden per jaar — Hogeschool Utrecht

| Jaar | Hogeschool Utrecht | Universiteit Utrecht | Hogeschool Amersfoort |
|------|-------------------|---------------------|----------------------|
| 2019 | 7.245             | 8.120               | 2.340                |
| 2020 | 7.510             | 8.450               | 2.280                |
| 2021 | 7.890             | 8.780               | 2.410                |
| 2022 | 8.120             | 9.100               | 2.520                |
| 2023 | 8.450             | 9.350               | 2.680                |

De Hogeschool Utrecht laat een **stijgende trend** zien met een groei van circa 16,6% over vijf jaar. De instelling blijft daarmee de grootste hbo-aanbieder in de regio.

## Verdeling naar sector

| Sector | Gediplomeerden 2023 | Aandeel |
|--------|--------------------:|--------:|
| Economie | 2.850 | 33,7% |
| Gezondheidszorg | 1.920 | 22,7% |
| Techniek | 1.350 | 16,0% |
| Onderwijs | 1.180 | 14,0% |
| Gedrag & Maatschappij | 780 | 9,2% |
| Taal & Cultuur | 370 | 4,4% |

**Economie** is veruit de grootste sector, gevolgd door **Gezondheidszorg**. De sector Techniek groeit het snelst met +12% ten opzichte van 2022.

## Instroom vs. uitstroom

| Jaar | Instroom eerstejaars | Uitstroom gediplomeerden | Rendement |
|------|---------------------:|-------------------------:|----------:|
| 2019 | 9.800 | 7.245 | 73,9% |
| 2020 | 10.120 | 7.510 | 74,2% |
| 2021 | 10.450 | 7.890 | 75,5% |
| 2022 | 10.680 | 8.120 | 76,0% |
| 2023 | 11.200 | 8.450 | 75,4% |

Het diplomarendement schommelt rond de **75%**, wat boven het landelijk hbo-gemiddelde van 71% ligt.`,
    done: true,
  },
  {
    id: 3,
    role: 'user',
    content: 'Kun je ook de man/vrouw verdeling laten zien?',
    done: true,
  },
  {
    id: 4,
    role: 'assistant',
    content: `## Geslachtsverdeling ingeschrevenen — Hogeschool Utrecht

| Jaar | Vrouw | Man | Totaal | % Vrouw |
|------|------:|----:|-------:|--------:|
| 2019 | 18.400 | 15.200 | 33.600 | 54,8% |
| 2020 | 19.100 | 15.800 | 34.900 | 54,7% |
| 2021 | 19.850 | 16.300 | 36.150 | 54,9% |
| 2022 | 20.200 | 16.900 | 37.100 | 54,4% |
| 2023 | 20.800 | 17.400 | 38.200 | 54,5% |

De verhouding is stabiel: circa **55% vrouw** en **45% man**. Dit is vergelijkbaar met het landelijk hbo-gemiddelde.

Per sector zijn er wel duidelijke verschillen:
- **Gezondheidszorg**: 82% vrouw
- **Techniek**: 19% vrouw
- **Economie**: 48% vrouw
- **Onderwijs**: 71% vrouw`,
    done: true,
  },
]

const SEED_FIGURES = []

export function seedDashboardChat() {
  sessionStorage.setItem(DC_MESSAGES_KEY, JSON.stringify(SEED_MESSAGES))
  sessionStorage.setItem(DC_FIGURES_KEY, JSON.stringify(SEED_FIGURES))
}

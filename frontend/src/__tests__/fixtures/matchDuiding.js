// `match_duiding` zoals data/dashboard.py (_match_duiding) het geeft sinds #1225: de vacatures van CBS 83599NED,
// gemiddeld over de laatste vier kwartalen (uit het opgenomen CBS-antwoord van tests/fixtures/cbs/, 26-11-2026), de
// koppeltabel van data/sbi_onderwijssector.csv en de uitleg. Tests die een ander getal willen, spreiden dit object.
export const MATCH_DUIDING = {
  drempel: 1.2,
  min_gediplomeerden: 30,
  vacatures: {
    bron: 'CBS',
    dataset: '83599NED',
    titel: 'Openstaande vacatures; SBI 2008, regio',
    url: 'https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table',
    licentie: 'CC BY 4.0',
    periode: '2025 4e kwartaal t/m 2026 3e kwartaal',
    perioden: ['2025 4e kwartaal', '2026 1e kwartaal', '2026 2e kwartaal', '2026 3e kwartaal'],
    kwartalen: 4,
    voorlopig: true,
  },
  peildatum_ouderdom_maanden: 1,
  verouderd: false,
  diplomajaren: [2023, 2024, 2025],
  roa_versie: 'v20260901',
  koppeltabel: { herkomst: 'met de hand opgesteld, geen taalmodel', bijgewerkt: '2026-11-26' },
  indicatief: true,
  uitleg: 'De vacatures tellen per bedrijfstak van de werkgever (SBI), niet per beroep: een verpleegkundige in een fabriek telt bij de industrie. Welke bedrijfstakken bij een sector horen, staat in een koppeltabel van deze app. Het label per sector is daarom indicatief.',
}

// ─── localStorage / sessionStorage keys ─────────────────────────────────────
export const STORAGE_WORKBOOKS = 'edudata_workbooks'
export const STORAGE_CONVERSATIONS = 'openEDUdata_conversations'
export const STORAGE_SETTINGS = 'openEDUdata_settings'
export const STORAGE_ONBOARDED = 'openEDUdata_onboarded'
export const STORAGE_TOKEN = 'edudata_token'
export const STORAGE_DC_MESSAGES = 'edudata_dc_messages'
export const STORAGE_DC_FIGURES = 'edudata_dc_figures'

// ─── Shared color palette ────────────────────────────────────────────────────
export const CHART_COLORS = ['#2563EB', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6', '#22C55E']

// ─── Magic numbers ───────────────────────────────────────────────────────────
export const MAX_CONVERSATIONS = 15
export const MIN_RESPONSE_LENGTH = 150
export const MAX_TEXTAREA_HEIGHT = 120
export const DEFAULT_INSTELLING = 'Hogeschool Utrecht'

// ─── Data sources & suggested questions ──────────────────────────────────────
export const SOURCES = [
  { label: 'DUO Open Data' },
  { label: '1cijferHO' },
  { label: 'CBS StatLine' },
  { label: 'UWV Arbeidsmarkt' },
  { label: 'ROA / SBB' },
]

export const SUGGESTED = [
  {
    category: 'Arbeidsmarkt',
    questions: [
      'Welk percentage van de bevolking in mijn regio neemt deel aan LLO?',
      'Wat is in mijn regio het opleidingsniveau van werkzoekenden?',
      'Hoeveel vacatures zijn er in mijn regio voor ons onderwijsaanbod?',
    ],
  },
  {
    category: 'Uitstroom',
    questions: [
      'Hoeveel gediplomeerden levert ons onderwijsaanbod op ten opzichte van andere instellingen in de regio?',
      'Wat verdienen gediplomeerden van onze instelling gemiddeld in de regio?',
      'Hoe groot is het aandeel voortijdig schoolverlaters dat werk heeft gevonden in mijn regio?',
    ],
  },
  {
    category: 'Instroom',
    questions: [
      'Waar komen mijn lerenden vandaan en met welke instellingen in de regio concurreer ik om dezelfde doelgroep?',
      'Hoeveel instromers komen rechtstreeks vanuit een andere opleiding uit de regio?',
      'Hoe heeft de deelname aan voltijdonderwijs bij ons zich ontwikkeld?',
    ],
  },
]

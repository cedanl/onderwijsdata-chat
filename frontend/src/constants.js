// ─── localStorage / sessionStorage keys ─────────────────────────────────────
export const STORAGE_WORKBOOKS = 'edudata_workbooks'
export const STORAGE_CONVERSATIONS = 'openEDUdata_conversations'
export const STORAGE_SETTINGS = 'openEDUdata_settings'
export const STORAGE_ONBOARDED = 'openEDUdata_onboarded'
export const STORAGE_TOKEN = 'edudata_token'
export const STORAGE_DC_MESSAGES = 'edudata_dc_messages'
export const STORAGE_DC_FIGURES = 'edudata_dc_figures'
export const STORAGE_CURRENT_CHAT = 'openEDUdata_current_chat'
export const STORAGE_MODEL = 'openEDUdata_model'

// ─── Shared color palette ────────────────────────────────────────────────────
export const CHART_COLORS = ['#2563EB', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6', '#22C55E', '#EC4899', '#6366F1']

export const COLOR_EIGEN = CHART_COLORS[0]
export const COLOR_DIPLOM = '#0D9488'
export const COLOR_EERSTEJAARS = '#22C55E'

// ─── Magic numbers ───────────────────────────────────────────────────────────
export const MAX_CONVERSATIONS = 15
export const MIN_RESPONSE_LENGTH = 150
export const MAX_TEXTAREA_HEIGHT = 120
export const DEFAULT_INSTELLING = 'Hogeschool Utrecht'

// ─── Chat context limits ──────────────────────────────────────────────────────
// MAX_HISTORY must match backend core/config.py MAX_HISTORY (default 40 = 20 turns)
export const MAX_HISTORY = 40
export const MAX_CHAT_TURNS = 20
export const WARN_CHAT_TURNS = 16

// ─── Suggested questions ──────────────────────────────────────────────────────
export const SUGGESTED = [
  {
    category: 'Arbeidsmarktmatch',
    questions: [
      'Hoe sluiten gediplomeerden van onze instelling aan op de vacatures in mijn regio?',
      'Wat is de arbeidsmarktvraag naar ons onderwijsaanbod?',
      'Hoe verhouden de sectoren van onze instelling zich tot de arbeidsmarkt in mijn regio?',
    ],
  },
  {
    category: 'Rendement & Diplomering',
    questions: [
      'Hoeveel gediplomeerden levert onze instelling af ten opzichte van de regio?',
      'Hoe verhouden de diploma-aantallen van onze instelling zich tot andere instellingen in mijn regio?',
      'Hoe groot is landelijk gezien het uitvalrisico in ons onderwijsaanbod?',
    ],
  },
  {
    category: 'Groei & Instroom',
    questions: [
      'Groeit de instroom bij ons sneller dan het gemiddelde in mijn regio?',
      'Met welke instellingen in mijn regio concurreert onze instelling om dezelfde doelgroep?',
      'Volgt het aantal inschrijvingen bij ons de trend in mijn regio?',
    ],
  },
  {
    category: 'Regionale Context',
    questions: [
      'Welke sectoren hebben het meeste arbeidsmarktpotentieel in mijn regio?',
      'Waar komen mijn lerenden vandaan en welke regio\'s zijn onze doelmarkt?',
      'Hoe verandert de studentenpopulatie in mijn regio?',
    ],
  },
]

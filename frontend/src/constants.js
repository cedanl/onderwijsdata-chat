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
// Each question must be answerable with the connected sources (#446): vacancies are a UWV
// snapshot per province (mei 2023), the ROA forecast is national, and hbo/wo dropout exists
// only nationally. No source links graduates to jobs.
// What the sources hold differs per sector (#447): only mbo files have the students' place of
// residence, and a university is usually the whole wo of its province. `sectoren` lists where
// a question holds; without a known sector only the questions that hold everywhere show.
export const SECTOREN = ['mbo', 'hbo', 'wo']

export const SUGGESTED = [
  {
    category: 'Arbeidsmarktmatch',
    questions: [
      { tekst: 'Hoe verhoudt het diploma-aanbod van onze instelling per sector zich tot de UWV-vacatures in mijn provincie (mei 2023)?', sectoren: SECTOREN },
      { tekst: 'Wat is volgens de landelijke ROA-prognose het arbeidsmarktperspectief van de brede sectoren in ons onderwijsaanbod?', sectoren: ['mbo', 'hbo'] },
      { tekst: 'Wat is volgens de landelijke ROA-cijfers het arbeidsmarktperspectief van masterafgestudeerden?', sectoren: ['wo'] },
    ],
  },
  {
    category: 'Rendement & Diplomering',
    questions: [
      { tekst: 'Hoe heeft het aantal gediplomeerden van onze instelling zich de afgelopen jaren ontwikkeld?', sectoren: SECTOREN },
      { tekst: 'Hoeveel gediplomeerden levert onze instelling af ten opzichte van de andere instellingen in mijn provincie?', sectoren: ['mbo', 'hbo'] },
      { tekst: 'Hoe verhouden de diploma-aantallen van onze instelling zich tot die van de andere universiteiten?', sectoren: ['wo'] },
      { tekst: 'Hoe groot is landelijk gezien het uitvalrisico in ons onderwijsaanbod?', sectoren: ['mbo'] },
      { tekst: 'Hoeveel studenten verlaten landelijk het hbo zonder diploma?', sectoren: ['hbo'] },
      { tekst: 'Hoeveel studenten verlaten landelijk het wo zonder diploma?', sectoren: ['wo'] },
    ],
  },
  {
    category: 'Groei & Instroom',
    questions: [
      { tekst: 'Hoe heeft het aantal inschrijvingen bij onze instelling zich de afgelopen vijf jaar ontwikkeld?', sectoren: SECTOREN },
      { tekst: 'Groeit de instroom bij ons sneller dan het gemiddelde in mijn provincie?', sectoren: ['mbo', 'hbo'] },
      { tekst: 'Groeit de instroom bij ons sneller dan in het wo als geheel?', sectoren: ['wo'] },
      { tekst: 'Met welke instellingen concurreert onze instelling om studenten uit dezelfde woongemeenten?', sectoren: ['mbo'] },
      { tekst: 'Welke andere hogescholen in mijn provincie bieden opleidingen in dezelfde sectoren aan als onze instelling?', sectoren: ['hbo'] },
      { tekst: 'Welke andere universiteiten bieden opleidingen in dezelfde sectoren aan als onze instelling?', sectoren: ['wo'] },
    ],
  },
  {
    category: 'Regionale Context',
    questions: [
      { tekst: 'Voor welke sectoren stonden in mijn provincie de meeste UWV-vacatures open (mei 2023)?', sectoren: SECTOREN },
      { tekst: 'Waar komen mijn lerenden vandaan en welke regio\'s vormen de doelmarkt van onze instelling?', sectoren: ['mbo'] },
      { tekst: 'Hoe verandert het aantal mbo-studenten dat in mijn provincie woont?', sectoren: ['mbo'] },
      { tekst: 'Hoe verandert het aantal hbo-studenten bij de hogescholen in mijn provincie?', sectoren: ['hbo'] },
    ],
  },
]

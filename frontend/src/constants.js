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
// snapshot per province (mei 2023), the ROA forecast is national, and ho dropout exists only
// nationally, in the CBS cohort tables (CH-43). No source links graduates to jobs.
// What the sources hold differs per sector (#447): only mbo files have the students' place of
// residence (woongemeente per instelling), and a university is usually the whole wo of its
// province. `sectoren` lists where a question holds; without a known sector only the
// questions that hold everywhere show.
// One question per subject (CH-43): where the sectors differ, `{variant}` in `tekst` takes the
// text for the sector from `varianten`, or `standaard` when the sector is unknown.
// `profiel: true` needs an institution in the profile; `profiel: false` shows only without one,
// so a demo never asks about "onze instelling" the chat does not know (CH-42, #465).
export const SECTOREN = ['mbo', 'hbo', 'wo']

const ANDERE_INSTELLINGEN = {
  mbo: 'de andere mbo-instellingen in mijn provincie',
  hbo: 'de andere hogescholen in mijn provincie',
  wo: 'de andere universiteiten',
  standaard: 'de andere instellingen in mijn provincie',
}

export const SUGGESTED = [
  {
    category: 'Arbeidsmarktmatch',
    questions: [
      { tekst: 'Hoe verhoudt het diploma-aanbod van onze instelling per sector zich tot de UWV-vacatures in mijn provincie (mei 2023)?', sectoren: SECTOREN, profiel: true },
      {
        tekst: 'Wat is volgens de landelijke ROA-prognose het arbeidsmarktperspectief van {variant}?',
        sectoren: SECTOREN,
        profiel: true,
        varianten: { mbo: 'de brede sectoren in ons onderwijsaanbod', hbo: 'de brede sectoren in ons onderwijsaanbod', wo: 'masterafgestudeerden', standaard: 'de brede sectoren in ons onderwijsaanbod' },
      },
      { tekst: 'Voor welke sectoren stonden per provincie de meeste UWV-vacatures open (mei 2023)?', sectoren: SECTOREN, profiel: false },
      { tekst: 'Wat is volgens de landelijke ROA-prognose het arbeidsmarktperspectief per brede sector in het mbo en hbo?', sectoren: SECTOREN, profiel: false },
    ],
  },
  {
    category: 'Rendement & Diplomering',
    questions: [
      { tekst: 'Hoe heeft het aantal gediplomeerden van onze instelling zich de afgelopen jaren ontwikkeld?', sectoren: SECTOREN, profiel: true },
      { tekst: 'Hoeveel gediplomeerden levert onze instelling af ten opzichte van {variant}?', sectoren: SECTOREN, profiel: true, varianten: ANDERE_INSTELLINGEN },
      { tekst: 'Hoe groot is landelijk gezien het uitvalrisico in ons onderwijsaanbod?', sectoren: ['mbo'], profiel: true },
      {
        tekst: 'Welk deel van de {variant}-instromers heeft na vijf jaar een diploma (CBS-cohorten)?',
        sectoren: SECTOREN,
        varianten: { mbo: 'mbo', hbo: 'hbo', wo: 'wo', standaard: 'mbo-, hbo- en wo' },
      },
    ],
  },
  {
    category: 'Groei & Instroom',
    questions: [
      { tekst: 'Hoe heeft het aantal inschrijvingen bij onze instelling zich de afgelopen vijf jaar ontwikkeld?', sectoren: SECTOREN, profiel: true },
      {
        tekst: 'Groeit de instroom bij ons sneller dan {variant}?',
        sectoren: SECTOREN,
        profiel: true,
        varianten: { mbo: 'het gemiddelde in mijn provincie', hbo: 'het gemiddelde in mijn provincie', wo: 'in het wo als geheel', standaard: 'het gemiddelde in mijn provincie' },
      },
      {
        tekst: 'Welke van {variant} bieden opleidingen in dezelfde sectoren aan als onze instelling?',
        sectoren: SECTOREN,
        profiel: true,
        varianten: ANDERE_INSTELLINGEN,
      },
      { tekst: 'Uit welke woongemeenten komen de studenten van onze instelling, en welke andere mbo-instellingen hebben studenten uit dezelfde gemeenten?', sectoren: ['mbo'], profiel: true },
      { tekst: 'Hoe heeft het aantal studenten in het mbo, hbo en wo zich landelijk ontwikkeld in de afgelopen vijf jaar?', sectoren: SECTOREN, profiel: false },
    ],
  },
  {
    category: 'Regionale Context',
    questions: [
      {
        tekst: 'Hoe verandert het aantal {variant}?',
        sectoren: ['mbo', 'hbo'],
        profiel: true,
        varianten: { mbo: 'mbo-studenten dat in mijn provincie woont', hbo: 'hbo-studenten bij de hogescholen in mijn provincie' },
      },
      { tekst: 'In welke provincies wonen de meeste mbo-studenten, en hoe verandert dat?', sectoren: SECTOREN, profiel: false },
    ],
  },
]

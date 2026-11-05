// @vitest-environment jsdom
// #933: de galerijkaart van een vast dashboard toont de echte bovenkant van dat dashboard, verkleind en niet bedienbaar,
// met de cijfers van de gekozen instelling. Zoals bij rapporten (#633) laadt alleen een kaart op of vlak bij het scherm,
// en het dashboard erachter gebruikt dezelfde lading: openen na de miniatuur vraagt de server niets nieuws.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import dashboards from './fixtures/dashboards.json'

vi.mock('react-chartjs-2', () => ({ Bar: function BarStub() { return null }, Line: function LineStub() { return null } }))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

const api = vi.hoisted(() => ({ fetchDashboardData: vi.fn(), fetchWorkbooks: vi.fn(async () => []) }))
vi.mock('../api', async importOriginal => ({ ...(await importOriginal()), ...api }))

import DashboardGallery from '../components/DashboardGallery'
import DashboardPage from '../pages/DashboardPage'
import { DashboardLadingen, useRegioDashboardData } from '../components/dashboards/shared/hooks'
import { BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL } from '../workbooks'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.ResizeObserver ??= class { observe() {} disconnect() {} }

const HU = 'Hogeschool Utrecht'
const VASTE = [BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL]
const MIJN = BUILTIN_MIJN_INSTELLING.id
const MARKT = BUILTIN_ARBEIDSMARKT.id
const LAND = BUILTIN_NATIONAAL.id

const HBO = dashboards.regio
// Wo: dezelfde ho-payload met het nationale wo-gemiddelde als benchmark; mbo: een eerstejaarsreeks die achterloopt.
const WO = {
  ...HBO,
  instelling: 'Universiteit Utrecht',
  benchmark: { ...HBO.benchmark, label: 'Nationaal WO gemiddelde (excl. eigen instelling)', regio_type: 'nationaal' },
}
const MBO = { ...HBO, type: 'mbo', instelling: 'ROC van Amsterdam', eerstejaars: { 2023: 11000, 2024: 11602 }, geslacht: undefined }

let payloads
let root
let container
let waarnemers

const fout = (status, message) => Object.assign(new Error(message), { status })

// Elke kaart heeft zijn eigen waarnemer; `inBeeld` speelt het scrollen na voor één kaart.
function nabootsen() {
  waarnemers = new Map()
  globalThis.IntersectionObserver = class {
    constructor(cb) { this.cb = cb }
    observe(el) { waarnemers.set(el, this.cb) }
    disconnect() {}
  }
}

beforeEach(() => {
  nabootsen()
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  payloads = {
    '/api/dashboard/regio': HBO,
    '/api/dashboard/rendement': dashboards.rendement,
    '/api/dashboard/nationaal': dashboards.nationaal,
    '/api/dashboard/arbeidsmarktmatch': dashboards.arbeidsmarktmatch,
  }
  api.fetchDashboardData.mockReset()
  api.fetchDashboardData.mockImplementation(async endpoint => {
    const p = payloads[endpoint]
    return typeof p === 'function' ? p() : p
  })
})

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  delete globalThis.IntersectionObserver
  delete window.matchMedia
})

async function toon(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

const galerij = (instelling = HU) => createElement(DashboardLadingen, null,
  createElement(DashboardGallery, { workbooks: VASTE, instelling, onSelect: vi.fn(), onDelete: vi.fn() }))

const kaart = id => container.querySelector(`.wb-card[data-wb-id="${id}"]`)
const miniatuur = id => kaart(id).querySelector('.wb-miniatuur')
const aanroepen = () => api.fetchDashboardData.mock.calls.map(([endpoint]) => endpoint)

async function inBeeld(id, ja = true) {
  await act(async () => { waarnemers.get(miniatuur(id))([{ isIntersecting: ja }]) })
}

async function alleInBeeld() {
  for (const id of [MIJN, MARKT, LAND]) await inBeeld(id)
}

describe('miniatuur van een vast dashboard (#933): alleen in beeld', () => {
  it('haalt niets op zolang de kaarten buiten beeld zijn', async () => {
    await toon(galerij())
    expect(aanroepen()).toEqual([])
    for (const id of [MIJN, MARKT, LAND]) expect(miniatuur(id).querySelector('.wb-preview-shimmer')).not.toBeNull()
  })

  it('haalt voor een kaart die in beeld komt één lading op, alleen voor die kaart', async () => {
    await toon(galerij())
    await inBeeld(MIJN)
    expect(aanroepen()).toEqual(['/api/dashboard/regio'])
    expect(api.fetchDashboardData.mock.calls[0][1]).toBe(HU)
    expect(miniatuur(MARKT).querySelector('.wb-preview-shimmer')).not.toBeNull()
  })

  it('opent de galerij met drie aanroepen als alle kaarten in beeld zijn: één per dashboard', async () => {
    await toon(galerij())
    await alleInBeeld()
    expect(aanroepen().sort()).toEqual(['/api/dashboard/arbeidsmarktmatch', '/api/dashboard/nationaal', '/api/dashboard/regio'])
  })

  it('vraagt het een tweede keer niet opnieuw: uit beeld en weer terug', async () => {
    await toon(galerij())
    await inBeeld(MIJN)
    await inBeeld(MIJN, false)
    expect(miniatuur(MIJN).textContent).not.toContain('Kerncijfers')
    await inBeeld(MIJN)
    expect(aanroepen()).toEqual(['/api/dashboard/regio'])
    expect(miniatuur(MIJN).textContent).toContain('35.058')
  })
})

describe('miniatuur van een vast dashboard (#933): de echte bovenkant', () => {
  it('Mijn instelling: de kerncijfers van de instelling', async () => {
    await toon(galerij())
    await inBeeld(MIJN)
    const tekst = miniatuur(MIJN).textContent
    expect(tekst).toContain('Kerncijfers')
    expect(tekst).toContain('Ingeschrevenen 2025')
    expect(tekst).toContain('35.058')
    expect(tekst).toContain('Gediplomeerden 2024')
    expect(tekst).toContain('6.438')
  })

  it('Arbeidsmarkt: de match score per sector', async () => {
    await toon(galerij())
    await inBeeld(MARKT)
    const tekst = miniatuur(MARKT).textContent
    expect(tekst).toContain('Match score')
    expect(tekst).toContain('Techniek')
    expect(tekst).toContain('Schaarste')
  })

  it('Landelijk: de positie per sector', async () => {
    await toon(galerij())
    await inBeeld(LAND)
    const tekst = miniatuur(LAND).textContent
    expect(tekst).toContain('Positie per sector')
    expect(tekst).toContain('Gezondheidszorg')
    expect(tekst).toContain('#1')
  })

  it('tekent geen grafiek en geen kaart: geen canvas, geen Plotly', async () => {
    await toon(galerij())
    await alleInBeeld()
    expect(container.querySelector('.wb-miniatuur canvas, .wb-miniatuur .js-plotly-plot')).toBeNull()
  })

  it.each([
    ['hbo', HBO, 'Gem. arbeidsmarktregio gemiddelde'],
    ['wo', WO, 'Gem. nationaal wo gemiddelde'],
    ['mbo', MBO, 'Gem. arbeidsmarktregio gemiddelde'],
  ])('%s: de kerncijfers volgen het niveau van de instelling', async (_niveau, regio, benchmark) => {
    payloads['/api/dashboard/regio'] = regio
    await toon(galerij(regio.instelling))
    await inBeeld(MIJN)
    expect(api.fetchDashboardData.mock.calls[0][1]).toBe(regio.instelling)
    const tekst = miniatuur(MIJN).textContent
    expect(tekst).toContain(`${regio.instelling} vs. `)
    expect(tekst).toContain(benchmark)
    expect(tekst).toContain('35.058')
  })

  it('mbo: geen tegel "Aandeel vrouw" zonder geslachtsdata, wel de eerstejaars van de bron', async () => {
    payloads['/api/dashboard/regio'] = MBO
    await toon(galerij(MBO.instelling))
    await inBeeld(MIJN)
    const tekst = miniatuur(MIJN).textContent
    expect(tekst).not.toContain('Aandeel vrouw')
    expect(tekst).toContain('Eerstejaars 2024')
    expect(tekst).toContain('11.602')
  })
})

describe('miniatuur van een vast dashboard (#933): laden, niet gevonden en fout', () => {
  it('laadt met een glans, zonder foutbalk of lege witte kaart', async () => {
    payloads['/api/dashboard/regio'] = () => new Promise(() => {})
    await toon(galerij())
    await inBeeld(MIJN)
    expect(miniatuur(MIJN).querySelector('.wb-preview-shimmer')).not.toBeNull()
    expect(miniatuur(MIJN).textContent).toBe('')
  })

  it('zegt in de kaart dat de instelling niet gevonden is', async () => {
    payloads['/api/dashboard/regio'] = { gevonden: false, beschikbare_instellingen: ['Hogeschool Rotterdam'] }
    await toon(galerij('Hogeschool Nergens'))
    await inBeeld(MIJN)
    const melding = miniatuur(MIJN).querySelector('.wb-miniatuur-melding')
    expect(melding.textContent).toContain('niet gevonden')
    expect(melding.textContent).toContain('Hogeschool Nergens')
  })

  it('zegt in de kaart dat de cijfers niet laadden, en de andere kaarten tonen hun cijfers', async () => {
    payloads['/api/dashboard/regio'] = () => Promise.reject(fout(503, 'De DUO-data is nu niet beschikbaar.'))
    await toon(galerij())
    await alleInBeeld()
    const melding = miniatuur(MIJN).querySelector('.wb-miniatuur-melding')
    expect(melding.textContent).toMatch(/niet .*geladen/)
    expect(melding.textContent).not.toMatch(/API \d|voorbeeld/i)
    expect(miniatuur(MARKT).textContent).toContain('Match score')
    expect(miniatuur(LAND).textContent).toContain('Positie per sector')
  })

  it('toont een melding als de bovenkant leeg is, geen witte kaart', async () => {
    payloads['/api/dashboard/arbeidsmarktmatch'] = { ...dashboards.arbeidsmarktmatch, match_score: null }
    await toon(galerij())
    await inBeeld(MARKT)
    expect(miniatuur(MARKT).querySelector('.wb-miniatuur-melding').textContent).toContain('Open het dashboard')
  })
})

describe('miniatuur van een vast dashboard (#933): alleen kijken', () => {
  it('is verborgen voor hulpsoftware en inert, met niets om te focussen of te klikken', async () => {
    await toon(galerij())
    await alleInBeeld()
    for (const id of [MIJN, MARKT, LAND]) {
      const m = miniatuur(id)
      expect(m.getAttribute('aria-hidden')).toBe('true')
      expect(m.hasAttribute('inert')).toBe(true)
      expect(m.querySelectorAll('a, button, input, select, textarea, [tabindex], [role="alert"], [role="status"]')).toHaveLength(0)
    }
  })

  it('laat de kaart één link met één naam: geen kopjes of tekst van de miniatuur in de naam', async () => {
    await toon(galerij())
    await alleInBeeld()
    const k = kaart(MIJN)
    expect(k.tagName).toBe('A')
    expect(k.querySelectorAll('a, button')).toHaveLength(0)
    // Elk kopje van de miniatuur valt onder aria-hidden; de galerij houdt haar eigen koppen.
    for (const kop of container.querySelectorAll('.wb-card h1, .wb-card h2, .wb-card h3')) {
      expect(kop.closest('[aria-hidden="true"]')).not.toBeNull()
    }
  })
})

describe('het dashboard na de miniatuur (#933)', () => {
  async function pagina() {
    await toon(createElement(MemoryRouter, { initialEntries: ['/dashboards'] },
      createElement(DashboardPage, { settings: { instelling: HU } })))
  }

  async function open(id) {
    await act(async () => { kaart(id).click() })
    await act(async () => { await new Promise(r => setTimeout(r, 0)) })
  }

  it('opent zonder tweede lading van wat de miniatuur al had', async () => {
    await pagina()
    await inBeeld(MIJN)
    expect(aanroepen()).toEqual(['/api/dashboard/regio'])
    await open(MIJN)
    expect(container.querySelector('.dashboard-content').textContent).toContain('Kerncijfers')
    expect(aanroepen().sort()).toEqual(['/api/dashboard/regio', '/api/dashboard/rendement'])
  })

  it('deelt de lading die de miniatuur nog doet', async () => {
    let klaar
    payloads['/api/dashboard/regio'] = () => new Promise(r => { klaar = () => r(HBO) })
    await pagina()
    await inBeeld(MIJN)
    await open(MIJN)
    await act(async () => { klaar() })
    expect(container.querySelector('.dashboard-content').textContent).toContain('Kerncijfers')
    expect(aanroepen().filter(e => e === '/api/dashboard/regio')).toHaveLength(1)
  })

  it('Arbeidsmarkt hergebruikt de lading van beide miniaturen: geen enkele nieuwe aanroep', async () => {
    await pagina()
    await alleInBeeld()
    expect(aanroepen()).toHaveLength(3)
    await open(MARKT)
    expect(aanroepen()).toHaveLength(3)
  })
})

describe('gedeelde lading (#933)', () => {
  let stand
  function Probe({ instelling }) {
    stand = useRegioDashboardData(instelling)
    return null
  }

  it('bewaart een mislukte lading niet: een nieuwe poging vraagt de server opnieuw', async () => {
    api.fetchDashboardData
      .mockRejectedValueOnce(fout(503, 'De DUO-data is nu niet beschikbaar.'))
      .mockResolvedValueOnce(HBO)
    await toon(createElement(DashboardLadingen, null, createElement(Probe, { instelling: HU })))
    expect(stand.error.herstelbaar).toBe(true)
    await act(async () => { stand.opnieuw() })
    expect(api.fetchDashboardData).toHaveBeenCalledTimes(2)
    expect(stand.data).toBe(HBO)
  })

  it('laadt opnieuw op "opnieuw", ook na een geslaagde lading (een deel kon niet laden, #901)', async () => {
    await toon(createElement(DashboardLadingen, null, createElement(Probe, { instelling: HU })))
    expect(stand.data).toBe(HBO)
    await act(async () => { stand.opnieuw() })
    expect(api.fetchDashboardData).toHaveBeenCalledTimes(2)
  })
})

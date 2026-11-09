// @vitest-environment jsdom
// #957: het dashboard Opleidingen. Per opleiding de cijfers uit de Studiekeuzedatabase naast het landelijke cijfer van
// LCSK, zonder rangorde of kleur als oordeel; een leeg vak is "geen cijfer", nooit 0; een oordeel op minder dan 30
// respondenten heet onzeker; de verplichte vermelding van LCSK staat in het bronblok. Alleen waar de sleutel staat.
// De payloads komen van de backend op de proefexport (tests/test_dashboard_opleidingen.py houdt ze gelijk).
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import payloads from './fixtures/dashboardOpleidingen.json'

const api = vi.hoisted(() => ({ fetchDashboardData: vi.fn(), fetchWorkbooks: vi.fn(async () => []) }))
vi.mock('../api', async importOriginal => ({ ...(await importOriginal()), ...api }))

import { InlineDashboardOpleidingen, sorteerOpleidingen, nseOnderschrift } from '../components/dashboards/opleidingen/index'
import { DashboardMiniatuur } from '../components/dashboards/miniatuur'
import { DashboardLadingen } from '../components/dashboards/shared/hooks'
import DashboardPage, { vasteDashboards, OPLEIDINGEN_NIET_HIER } from '../pages/DashboardPage'
import { BUILTIN_OPLEIDINGEN, opleidingenBeschrijving } from '../workbooks'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.ResizeObserver ??= class { observe() {} disconnect() {} }

const VERPLICHTE_ZIN = 'Er is gebruik gemaakt van de data van Landelijk Centrum Studiekeuze.'

let root
let container

beforeEach(() => {
  api.fetchDashboardData.mockReset()
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
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

async function dashboard(payload) {
  api.fetchDashboardData.mockResolvedValue(payload)
  await toon(createElement(InlineDashboardOpleidingen, { instelling: payload.instelling }))
}

const tabel = naam => container.querySelector(`.tabel-scroll[aria-label="${naam}"] table`)
const rijen = naam => [...tabel(naam).querySelectorAll('tbody tr')]
const cellen = tr => [...tr.querySelectorAll('td')].map(td => td.textContent)
const kolom = naam => [...tabel(naam).querySelectorAll('thead th')].map(th => th.textContent.replace(/ [▲▼]$/, ''))

describe('de opleidingentabel', () => {
  it('toont per opleiding en vorm het cijfer met het landelijke cijfer ernaast', async () => {
    await dashboard(payloads.hbo)
    expect(api.fetchDashboardData.mock.calls[0][0]).toBe('/api/dashboard/opleidingen')
    expect(kolom('Opleidingen')).toEqual([
      'Opleiding', 'CROHO', 'Graad', 'Vorm', 'Plaats', 'NSE-oordeel', 'NSE landelijk',
      'Doorstroom jaar 2', 'Diplomarendement', 'Rendement landelijk', 'Numerus fixus',
    ])
    const ict = rijen('Opleidingen').map(cellen).find(c => c[0] === 'ICT' && c[3] === 'voltijd')
    expect(ict.slice(1, 7)).toEqual(['30020', 'Bachelor', 'voltijd', 'Utrecht', '3,61n = 120', '3,53'])
    expect(ict[7]).toBe('70,0%')
    expect(ict[9]).toBe('50,0%')
    expect(ict[10]).toBe('nee')
    // Aantallen studenten en eerstejaars staan op Mijn instelling (DUO), niet hier (#878).
    expect(kolom('Opleidingen')).not.toContain('Studenten')
  })

  it('zegt "geen cijfer" bij een leeg vak, nooit 0', async () => {
    await dashboard(payloads.hbo)
    const deeltijd = rijen('Opleidingen').find(tr => cellen(tr)[0] === 'ICT' && cellen(tr)[3] === 'deeltijd')
    const [doorstroom, rendement] = [...deeltijd.querySelectorAll('td')].slice(7, 9)
    for (const td of [doorstroom, rendement]) {
      expect(td.textContent).toBe('—geen cijfer')
      expect(td.querySelector('.sr-only').textContent).toBe('geen cijfer')
    }
    // Het landelijke rendement staat er wel, en de HU is daar de enige aanbieder.
    expect(cellen(deeltijd)[9]).toBe('50,0%enige aanbieder')
  })

  it('noemt een oordeel op minder dan 30 respondenten onzeker, in woorden en niet als kleur', async () => {
    await dashboard(payloads.onzeker)
    const [rij] = rijen('Opleidingen')
    expect(cellen(rij)[5]).toBe('4,20n = 15 · onzeker')
    expect(rij.querySelector('[style*="color: rgb(2"], [style*="#DC"], [style*="#16A"]')).toBeNull()
    expect(nseOnderschrift({ nse_oordeel: null, nse_respondenten: 3, nse_onzeker: true })).toBeNull()
  })

  it('geeft geen label boven of onder landelijk en geen rangorde', async () => {
    await dashboard(payloads.hbo)
    expect(tabel('Opleidingen').textContent).not.toMatch(/boven|onder|beter|slechter|hoger|lager|rang|top \d/i)
    expect(container.textContent).not.toMatch(/ranking|top \d/i)
    expect(container.textContent).toContain('het dashboard rangschikt geen opleidingen of instellingen')
  })

  it('sorteert alleen op beschrijvende kolommen, standaard op naam', async () => {
    await dashboard(payloads.hbo)
    const sorteerbaar = [...tabel('Opleidingen').querySelectorAll('thead th button')].map(b => b.textContent.replace(/ [▲▼]$/, ''))
    expect(sorteerbaar).toEqual(['Opleiding', 'Graad', 'Vorm', 'Plaats'])
    const kop = tabel('Opleidingen').querySelector('thead th')
    expect(kop.getAttribute('aria-sort')).toBe('ascending')
    expect(rijen('Opleidingen').map(tr => cellen(tr)[0])).toEqual(['ICT', 'ICT', 'Verpleegkunde'])
    await act(async () => { kop.querySelector('button').click() })
    expect(kop.getAttribute('aria-sort')).toBe('descending')
    expect(rijen('Opleidingen').map(tr => cellen(tr)[0])).toEqual(['Verpleegkunde', 'ICT', 'ICT'])
  })

  it('sorteert binnen een kolom verder op naam, plaats en vorm', () => {
    const r = [
      { opleiding: 'B', plaats: 'Utrecht', vorm: 'voltijd', graad: 'Master' },
      { opleiding: 'A', plaats: 'Zwolle', vorm: 'voltijd', graad: 'Master' },
      { opleiding: 'A', plaats: 'Amersfoort', vorm: 'deeltijd', graad: 'Bachelor' },
    ]
    expect(sorteerOpleidingen(r).map(x => `${x.opleiding} ${x.plaats}`)).toEqual(['A Amersfoort', 'A Zwolle', 'B Utrecht'])
    expect(sorteerOpleidingen(r, 'graad').map(x => x.graad + x.opleiding)).toEqual(['BachelorA', 'MasterA', 'MasterB'])
    expect(sorteerOpleidingen(r, 'plaats', false).map(x => x.plaats)).toEqual(['Zwolle', 'Utrecht', 'Amersfoort'])
  })
})

describe('NSE-thema\'s, arbeidsmarkt en numerus fixus', () => {
  it('heeft de NSE-thema\'s per vorm achter een uitklap', async () => {
    await dashboard(payloads.hbo)
    const uitklap = container.querySelector('details.db-uitklap')
    expect(uitklap.querySelector('summary').textContent).toContain("NSE-thema's per opleidingsvorm")
    expect(kolom("NSE-thema's per opleidingsvorm")).toEqual(['Opleiding', 'Vorm', 'Respondenten', ...payloads.hbo.themas.map(t => t.naam)])
  })

  it('zegt bij de arbeidsmarkt dat het landelijke cijfers per rubriek zijn, en waarom een wo-bachelor leeg is', async () => {
    await dashboard(payloads.wo)
    expect(container.textContent).toContain('niet over de eigen afgestudeerden van deze instelling')
    const psy = rijen('Arbeidsmarkt van de opleidingsrichting').find(tr => cellen(tr)[0].startsWith('Psychologie'))
    expect(cellen(psy)[2]).toBe(payloads.wo.arbeidsmarkt.find(r => r.opleiding === 'Psychologie').reden_leeg)
  })

  it('toont de arbeidsmarkt van een hbo-bachelor met salaris, werkloosheid en baan op niveau', async () => {
    await dashboard(payloads.hbo)
    const ict = rijen('Arbeidsmarkt van de opleidingsrichting').map(cellen).find(c => c[0].startsWith('ICT'))
    expect(ict.slice(1)).toEqual(['HBO Bachelor', 'informatica', '€ 3.295', '2,5%', '80,0%', 'hbo - ict'])
  })

  it('toont numerus fixus met capaciteit, studiejaar en voertaal, of zegt dat er geen is', async () => {
    await dashboard(payloads.wo)
    expect(rijen('Numerus fixus').map(cellen).map(c => c.slice(2, 5))).toEqual([
      ['Voertaal-overstijgend', '2026', '60'],
      ['Voertaal-overstijgend', '2027', '71'],
    ])
    act(() => root.unmount())
    container.remove()
    root = undefined
    await dashboard(payloads.hbo)
    expect(container.textContent).toContain('Geen opleidingen met numerus fixus of decentrale selectie')
  })
})

describe('melding en bronvermelding', () => {
  it('geeft een mbo-instelling de vaste melding en geen tabellen', async () => {
    await dashboard(payloads.mbo)
    expect(container.textContent).toContain(payloads.mbo.melding)
    expect(container.querySelector('table')).toBeNull()
  })

  // #980, besluit B: een instelling die de Studiekeuzedatabase kent maar het DUO-register niet, is niet "niet gevonden".
  it('noemt bij een instelling buiten het DUO-register de grens, niet "niet gevonden in DUO-data"', async () => {
    await dashboard(payloads.buiten_register)
    expect(container.textContent).toContain(payloads.buiten_register.melding)
    expect(container.textContent).toContain('de Studiekeuzedatabase heeft er wel gegevens over')
    expect(container.textContent).not.toContain('niet gevonden')
    expect(container.querySelector('table')).toBeNull()
    expect(container.querySelector('.dashboard-sources').textContent).toContain(VERPLICHTE_ZIN)
  })

  it('noemt LCSK met versie, jaren, link en de verplichte zin', async () => {
    await dashboard(payloads.hbo)
    const bronnen = container.querySelector('.dashboard-sources')
    expect(bronnen.textContent).toContain(VERPLICHTE_ZIN)
    expect(bronnen.textContent).toContain('versie 26.6, export van 2026-11-06, NSE 2026, 1cijferHO 2025/26')
    expect(bronnen.querySelector('a').getAttribute('href')).toBe('https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/')
  })
})

describe('in de galerij', () => {
  it('staat er alleen waar de Studiekeuzedatabase antwoord geeft', () => {
    expect(vasteDashboards({}).map(b => b.id)).not.toContain(BUILTIN_OPLEIDINGEN.id)
    expect(vasteDashboards({ studiekeuze: false })).toHaveLength(3)
    expect(vasteDashboards({ studiekeuze: true }).map(b => b.id)).toContain(BUILTIN_OPLEIDINGEN.id)
  })

  it('zegt op de kaart van een mbo-instelling dat het dashboard alleen hbo en wo heeft', () => {
    expect(opleidingenBeschrijving('mbo')).toMatch(/alleen voor hogescholen en universiteiten/i)
    expect(opleidingenBeschrijving('hbo')).toContain('naast landelijk')
  })

  it('toont de kaart met de miniatuur van de kerncijfers', async () => {
    let zie
    globalThis.IntersectionObserver = class { constructor(cb) { zie = cb } observe() {} disconnect() {} }
    api.fetchDashboardData.mockResolvedValue(payloads.hbo)
    await toon(createElement(DashboardLadingen, null, createElement(DashboardMiniatuur, { wb: BUILTIN_OPLEIDINGEN, instelling: 'Hogeschool Utrecht' })))
    await act(async () => { zie([{ isIntersecting: true }]) })
    expect(container.textContent).toContain('Opleidingsvormen')
    expect(container.querySelector('.kpi-value').textContent).toBe('2')
  })

  it('toont in de miniatuur van een mbo-instelling de vaste melding', async () => {
    let zie
    globalThis.IntersectionObserver = class { constructor(cb) { zie = cb } observe() {} disconnect() {} }
    api.fetchDashboardData.mockResolvedValue(payloads.mbo)
    await toon(createElement(DashboardLadingen, null, createElement(DashboardMiniatuur, { wb: BUILTIN_OPLEIDINGEN, instelling: 'ROC Midden Nederland' })))
    await act(async () => { zie([{ isIntersecting: true }]) })
    expect(container.querySelector('.wb-miniatuur-melding').textContent).toBe(payloads.mbo.melding)
  })

  it('toont in de miniatuur van een instelling buiten het DUO-register de grensmelding', async () => {
    let zie
    globalThis.IntersectionObserver = class { constructor(cb) { zie = cb } observe() {} disconnect() {} }
    api.fetchDashboardData.mockResolvedValue(payloads.buiten_register)
    await toon(createElement(DashboardLadingen, null, createElement(DashboardMiniatuur, { wb: BUILTIN_OPLEIDINGEN, instelling: 'Proefuniversiteit' })))
    await act(async () => { zie([{ isIntersecting: true }]) })
    expect(container.querySelector('.wb-miniatuur-melding').textContent).toBe(payloads.buiten_register.melding)
  })

  it('opent via een link niet waar de bron ontbreekt, en zegt waarom', async () => {
    globalThis.IntersectionObserver = class { observe() {} disconnect() {} }
    await toon(createElement(MemoryRouter, { initialEntries: [`/dashboards?id=${BUILTIN_OPLEIDINGEN.id}`] },
      createElement(DashboardPage, { settings: {}, bronnen: {} })))
    expect(container.querySelector('.wb-gallery-notice').textContent).toBe(OPLEIDINGEN_NIET_HIER)
    expect(container.querySelectorAll('.wb-card')).toHaveLength(3)
  })

  it('heeft vier kaarten waar de bron er is', async () => {
    globalThis.IntersectionObserver = class { observe() {} disconnect() {} }
    await toon(createElement(MemoryRouter, { initialEntries: ['/dashboards'] },
      createElement(DashboardPage, { settings: {}, bronnen: { studiekeuze: true } })))
    expect([...container.querySelectorAll('.wb-card')].map(k => k.dataset.wbId)).toContain(BUILTIN_OPLEIDINGEN.id)
  })
})

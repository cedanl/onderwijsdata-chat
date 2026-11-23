// @vitest-environment jsdom
// #1127: een afgedrukt dashboard had alleen de inhoud: geen naam van het dashboard, geen afdrukdatum en geen productnaam,
// terwijl de rapport-PDF sinds #1037 een Npuls-printkop heeft. De printkop komt uit dezelfde tokens (npulsHuisstijl.js),
// staat op het scherm uit en komt alleen in de afdruk.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

vi.mock('../components/dashboards', async () => {
  const { createElement: maak } = await import('react')
  const stub = naam => function Stub({ instelling }) { return maak('p', { className: 'dashboard-content', 'data-dashboard': naam }, instelling) }
  return { InlineDashboardNationaal: stub('nationaal') }
})

import DashboardPrintkop, { afdrukDatum } from '../components/DashboardPrintkop'
import WorkbookViewer from '../components/WorkbookViewer'
import { BUILTIN_NATIONAAL } from '../workbooks'
import { NPULS, NPULS_LETTER, NPULS_LOGO_SVG, NPULS_PRODUCTNAAM } from '../npulsHuisstijl'
import { buildReportHtml } from '../reportHtml'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container
beforeEach(() => vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-20T10:00:00') }))
afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  vi.useRealTimers()
})

async function toon(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

// Wat jsdom van een kleur maakt, zodat de test de token vergelijkt en niet een vaste rgb-schrijfwijze.
const kleur = hex => { const el = document.createElement('i'); el.style.color = hex; return el.style.color }

describe('de printkop van een dashboard (#1127)', () => {
  it('noemt het dashboard, de instelling en de datum van afdrukken', async () => {
    await toon(createElement(DashboardPrintkop, { titel: 'Landelijk', instelling: 'Hogeschool Utrecht' }))
    const kop = container.querySelector('.db-printkop')
    expect(kop.querySelector('[data-onderdeel="titel"]').textContent).toBe('Landelijk')
    expect(kop.textContent).toContain('Hogeschool Utrecht')
    expect(kop.textContent).toContain('Afgedrukt op 20 november 2026')
  })

  it('draagt het Npuls-logo en de productnaam van de rapport-PDF, in de tokens van npulsHuisstijl.js', async () => {
    await toon(createElement(DashboardPrintkop, { titel: 'Landelijk', instelling: 'ROC van Flevoland' }))
    const kop = container.querySelector('.db-printkop')
    const merk = kop.querySelector('[data-onderdeel="merk"]')
    const logo = document.createElement('div')
    logo.innerHTML = NPULS_LOGO_SVG
    expect(merk.querySelector('svg').outerHTML).toBe(logo.firstChild.outerHTML)
    expect(merk.textContent).toBe(NPULS_PRODUCTNAAM)
    expect(NPULS_PRODUCTNAAM).toBe('EDUdata')
    expect(NPULS_LETTER).toContain('General Sans')
    expect(kop.style.fontFamily).toContain('General Sans')
    expect(kop.querySelector('[data-onderdeel="titel"]').style.color).toBe(kleur(NPULS.oranje))
    expect(kop.style.borderBottom).toContain('2px solid')
    expect(kop.style.borderBottom).toContain(kleur(NPULS.oranje))
  })

  it('zet dezelfde productnaam in de kop van de rapport-PDF', () => {
    expect(buildReportHtml({ title: 'Kort' })).toContain(`<span>${NPULS_PRODUCTNAAM}</span>`)
  })

  it('neemt de datum van het moment van afdrukken, niet van het openen van het dashboard', async () => {
    await toon(createElement(DashboardPrintkop, { titel: 'Landelijk', instelling: 'Hogeschool Utrecht' }))
    vi.setSystemTime(new Date('2026-11-21T09:00:00'))
    act(() => { window.dispatchEvent(new Event('beforeprint')) })
    expect(container.querySelector('.db-printkop').textContent).toContain('Afgedrukt op 21 november 2026')
  })

  it('laat de instelling weg als er geen is gekozen', async () => {
    await toon(createElement(DashboardPrintkop, { titel: 'Landelijk', instelling: '' }))
    expect(container.querySelector('[data-onderdeel="instelling"]')).toBeNull()
    expect(container.querySelector('.db-printkop').textContent).toContain('Afgedrukt op')
  })

  it('schrijft de datum zoals het rapport: dag, maand voluit en jaar', () => {
    expect(afdrukDatum(new Date('2026-03-05T12:00:00'))).toBe('5 maart 2026')
  })
})

describe('de printkop in de viewer van een vast dashboard (#1127)', () => {
  it('staat boven het dashboard, met de naam van het dashboard en de gekozen instelling', async () => {
    await toon(createElement(WorkbookViewer, { workbook: BUILTIN_NATIONAAL, instelling: 'Hogeschool Utrecht', onBack: vi.fn(), onUpdate: vi.fn() }))
    await act(async () => {})
    const inhoud = container.querySelector('.wb-viewer-content')
    const kop = inhoud.querySelector('.db-printkop')
    expect(kop.querySelector('[data-onderdeel="titel"]').textContent).toBe('Landelijk')
    expect(kop.textContent).toContain('Hogeschool Utrecht')
    expect(kop.compareDocumentPosition(inhoud.querySelector('.dashboard-content')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('hoort niet bij een rapport: dat heeft zijn eigen kop', async () => {
    await toon(createElement(WorkbookViewer, {
      workbook: { id: 'wb-1', type: 'report', title: 'Instroom hbo', htmlContent: '<p>rapport</p>' },
      instelling: 'Hogeschool Utrecht', onBack: vi.fn(), onUpdate: vi.fn(),
    }))
    expect(container.querySelector('.db-printkop')).toBeNull()
  })
})

describe('de print-CSS van een dashboard (#1127)', () => {
  const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')
  const print = css.slice(css.indexOf('@media print'))
  const scherm = css.slice(0, css.indexOf('@media print'))

  it('toont de printkop alleen op papier: op het scherm verandert niets', () => {
    expect(scherm).toContain('.db-printkop { display: none; }')
    expect(print).toMatch(/\.db-printkop \{ display: block;/)
  })

  it('drukt de viewer af, zodat de printkop en het dashboard samen over de volle lengte lopen', () => {
    expect(print).toContain('body:has(.dashboard-content) * { visibility: hidden; }')
    expect(print).toMatch(/body:has\(\.dashboard-content\) \.wb-viewer-content,\s*body:has\(\.dashboard-content\) \.wb-viewer-content \* \{ visibility: visible; \}/)
    expect(print).toMatch(/body:has\(\.dashboard-content\) \.wb-viewer-content \{ position: absolute; left: 0; top: 0; width: 100%;/)
    expect(print).toMatch(/body:has\(\.dashboard-content\) \.dashboard-content \{ padding: 0 !important;/)
  })
})

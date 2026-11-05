// @vitest-environment jsdom
// #916 en #921: de galerijkaart van een vast dashboard zegt wat het is (geen "Voorbeeld": de cijfers zijn live), de
// galerijtitel is een h1 die de focus houdt, en een externe bronlink meldt dat hij in een nieuw tabblad opent.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

// De previews en dashboards trekken Plotly binnen, dat jsdom niet kan laden.
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
// De miniaturen laden de cijfers van hun dashboard (#933); hier blijven ze laden, zonder netwerk.
vi.mock('../api', async importOriginal => ({ ...(await importOriginal()), fetchDashboardData: () => new Promise(() => {}) }))

import DashboardGallery from '../components/DashboardGallery'
import { DashboardSources, bronLabel } from '../components/dashboards/shared/shell'
import { BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL } from '../workbooks'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function toon(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const VASTE = [BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL]
const galerij = (extra = {}) => createElement(DashboardGallery, {
  workbooks: VASTE, instelling: 'Hogeschool Utrecht', onSelect: vi.fn(), onDelete: vi.fn(), ...extra,
})

describe('galerijkaart van een vast dashboard (#916)', () => {
  it('draagt op alle drie de kaarten hetzelfde label, en dat is niet "Voorbeeld"', async () => {
    await toon(galerij())
    const kaarten = [...container.querySelectorAll('.wb-card')]
    expect(kaarten).toHaveLength(3)
    const labels = kaarten.map(k => k.querySelector('.wb-builtin-badge').textContent)
    expect(new Set(labels)).toEqual(new Set(['Vast dashboard']))
    expect(container.textContent).not.toMatch(/voorbeeld/i)
  })

  it('laat de opgeslagen bouwer-dashboards bij hun eigen lijst, zonder het label van de vaste kaarten', async () => {
    await toon(galerij({ opgeslagen: [{ id: 'oud-1', title: 'Mijn bouwer-dashboard', createdAt: '2026-10-01T10:00:00Z' }] }))
    expect(container.querySelectorAll('.wb-builtin-badge')).toHaveLength(3)
    const item = container.querySelector('.wb-opgeslagen-item')
    expect(item.textContent).toContain('Mijn bouwer-dashboard')
    expect(item.querySelector('.wb-builtin-badge')).toBeNull()
  })
})

describe('galerijtitel (#921)', () => {
  it('is de enige h1 en kan de focus krijgen', async () => {
    await toon(galerij())
    const koppen = container.querySelectorAll('h1')
    expect(koppen).toHaveLength(1)
    expect(koppen[0].textContent).toBe('Dashboards')
    expect(koppen[0].classList.contains('wb-gallery-title')).toBe(true)
    expect(koppen[0].tabIndex).toBe(-1)
    act(() => koppen[0].focus())
    expect(document.activeElement).toBe(koppen[0])
  })
})

describe('bronlinks van een dashboard (#921)', () => {
  it('melden dat ze in een nieuw tabblad openen, in naam en met een zichtbare cue', async () => {
    // Regels van het bronblok uit de payload (#904).
    const bronnen = [
      { bron: 'DUO', dataset: 'p01hoinges', titel: 'Ingeschrevenen hoger onderwijs', url: 'https://onderwijsdata.duo.nl/dataset/p01hoinges' },
      { bron: 'DUO', dataset: 'mbo-studenten-per-instelling', titel: 'Mbo-studenten per instelling', url: 'https://onderwijsdata.duo.nl/dataset/mbo-studenten-per-instelling' },
    ]
    await toon(createElement(DashboardSources, { sources: bronnen }))
    const links = [...container.querySelectorAll('.dashboard-sources-list a')]
    expect(links).toHaveLength(bronnen.length)
    links.forEach((a, i) => {
      const label = bronLabel(bronnen[i])
      expect(a.getAttribute('target')).toBe('_blank')
      expect(a.getAttribute('rel')).toContain('noopener')
      expect(a.getAttribute('aria-label')).toBe(`${label} (opent in een nieuw tabblad)`)
      // De cue staat in de linktekst (CSS tekent het pictogram erachter), niet los naast de link.
      expect(a.querySelector('span').textContent).toBe(label)
    })
  })

  it('geeft niets terug zonder bronnen', async () => {
    await toon(createElement(DashboardSources, { sources: [] }))
    expect(container.querySelector('.dashboard-sources')).toBeNull()
  })
})

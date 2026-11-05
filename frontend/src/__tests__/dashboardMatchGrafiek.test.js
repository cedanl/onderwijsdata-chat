// @vitest-environment jsdom
// #949: vanaf acht sectoren staat de arbeidsmarktmatch als liggende staafgrafiek van `match_verhouding` met de drempels
// als stippellijn; onder de acht blijven de tegels. De grafiek heeft een tekstalternatief en een waardentabel (#905),
// het label staat in woorden in legenda en tabel, en de getallen in Nederlandse notatie (#904).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

// Zoals react-chartjs-2 zich gedraagt: een canvas met role="img"; data, opties en plugins gaan naar Chart.js en zijn
// hier na te lezen.
const getekend = []
vi.mock('react-chartjs-2', async () => {
  const { createElement: maak } = await import('react')
  const Canvas = ({ data, options, plugins, ...canvas }) => {
    getekend.push({ data, options, plugins })
    return maak('canvas', { role: 'img', ...canvas })
  }
  return { Line: Canvas, Bar: Canvas }
})

import { MatchScoreSection } from '../components/dashboards/arbeidsmarkt-consolidated/index'
import {
  buildMatchVerhoudingData, matchDrempels, MATCH_GRAFIEK_VANAF, MATCH_KAP,
} from '../components/dashboards/shared/charts-arbeidsmarkt'
import { DREMPELLIJNEN } from '../components/dashboards/shared/chart-opts'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const DUIDING = { drempel: 1.2, vacatures_peildatum: '2023-05-16', diplomajaren: [2023, 2024, 2025], sectormapping: {} }

// n sectoren met een score en een verhouding die bij dat label past.
function sectoren(n) {
  const labels = ['schaarste', 'evenwicht', 'overaanbod']
  const verhoudingen = { schaarste: 1.85, evenwicht: 1.05, overaanbod: 0.42 }
  const score = {}
  const verhouding = {}
  for (let i = 0; i < n; i++) {
    const label = labels[i % 3]
    score[`Sector ${i + 1}`] = label
    verhouding[`Sector ${i + 1}`] = verhoudingen[label] + i / 100
  }
  return { score, verhouding }
}

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  getekend.length = 0
})

function render(props) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(createElement(MatchScoreSection, { duiding: DUIDING, dark: false, ...props })))
}

describe('tegels of staafgrafiek (#949)', () => {
  it('drempel is acht sectoren', () => {
    expect(MATCH_GRAFIEK_VANAF).toBe(8)
  })

  it('zeven sectoren blijven tegels', () => {
    const { score, verhouding } = sectoren(7)
    render({ matchScore: score, verhouding })

    expect(container.querySelectorAll('.kpi-card')).toHaveLength(7)
    expect(container.querySelector('canvas')).toBeNull()
  })

  it('acht sectoren worden een staafgrafiek met de drempels als lijn, zonder tegels', () => {
    const { score, verhouding } = sectoren(8)
    render({ matchScore: score, verhouding })

    expect(container.querySelectorAll('.kpi-card')).toHaveLength(0)
    expect(container.querySelector('.chart-title').textContent).toBe('Match per sector')
    const { data, options, plugins } = getekend.at(-1)
    expect(data.labels).toHaveLength(8)
    expect(options.indexAxis).toBe('y')
    expect(plugins).toEqual([DREMPELLIJNEN])
    expect(options.plugins.drempellijnen.waarden).toEqual([1 / 1.2, 1.2])
    // De duiding van #900 blijft eronder staan.
    expect(container.querySelector('.db-match-duiding')).not.toBeNull()
  })

  it('telt alleen sectoren met een score: acht sectoren waarvan één zonder clusters blijven tegels', () => {
    const { score, verhouding } = sectoren(7)
    render({ matchScore: { ...score, ONDERWIJS: null }, verhouding: { ...verhouding, ONDERWIJS: null } })

    expect(container.querySelectorAll('.kpi-card')).toHaveLength(7)
    expect(container.textContent).toMatch(/Niet getoond \(geen beroepenclusters in de sectorindeling\): Onderwijs/)
  })

  it('een payload zonder verhoudingen krijgt de tegels', () => {
    const { score } = sectoren(9)
    render({ matchScore: score })

    expect(container.querySelectorAll('.kpi-card')).toHaveLength(9)
  })
})

describe('de grafiek is toegankelijk en Nederlands (#905, #904)', () => {
  it('heeft een tekstalternatief en een waardentabel met het label in woorden', () => {
    const { score, verhouding } = sectoren(8)
    render({ matchScore: score, verhouding })

    const canvas = container.querySelector('canvas')
    expect(canvas.getAttribute('role')).toBe('img')
    const naam = canvas.getAttribute('aria-label')
    expect(naam).toMatch(/^Staafdiagram: Match per sector\./)
    expect(naam).toContain('vacature-aandeel ÷ diploma-aandeel')
    expect(naam).toContain('Schaarste: 3 punten')

    const koppen = [...container.querySelectorAll('.waarden-details th')].map(th => th.textContent)
    expect(koppen).toEqual(expect.arrayContaining(['Sector', 'Schaarste', 'Evenwicht', 'Overaanbod']))
    expect(container.querySelector('.waarden-details').textContent).toContain('1,85')
  })

  it('noemt de drempels in tekst, in Nederlandse notatie', () => {
    const { score, verhouding } = sectoren(8)
    render({ matchScore: score, verhouding })

    expect(container.textContent).toContain('Boven 1,2 is het schaarste, onder 0,83 overaanbod')
    const { options } = getekend.at(-1)
    const tooltip = options.plugins.tooltip.callbacks.label({ dataset: { label: 'Schaarste' }, raw: 1.85 })
    expect(tooltip).toBe(' Schaarste: 1,85 keer')
  })

  it('volgt de drempel uit de payload', () => {
    const { score, verhouding } = sectoren(8)
    render({ matchScore: score, verhouding, duiding: { ...DUIDING, drempel: 1.5 } })

    expect(getekend.at(-1).options.plugins.drempellijnen.waarden).toEqual([1 / 1.5, 1.5])
    expect(container.textContent).toContain('Boven 1,5 is het schaarste, onder 0,67 overaanbod')
  })

  it('leest op 390 px: korte labels, een hoogte per sector en afgebroken namen op de as', () => {
    const { score, verhouding } = sectoren(17)
    render({ matchScore: { ...score, GEDRAG_EN_MAATSCHAPPIJ: 'evenwicht' }, verhouding: { ...verhouding, GEDRAG_EN_MAATSCHAPPIJ: 1 } })

    const { options } = getekend.at(-1)
    const hoogte = parseInt(container.querySelector('canvas').parentElement.style.height, 10)
    expect(hoogte).toBeGreaterThanOrEqual(18 * 30)
    // De categorie-as breekt lange namen af (labelRegels, #905), zoals de andere liggende staven.
    const regels = options.scales.y.ticks.callback.call({ getLabelForValue: () => 'Gedrag & Maatschappij' }, 0)
    expect(regels).toEqual(['Gedrag &', 'Maatschappij'])
  })
})

describe('buildMatchVerhoudingData', () => {
  it('sorteert aflopend, één reeks per label, en noemt een sector zonder verhouding', () => {
    const uit = buildMatchVerhoudingData(
      { TECHNIEK: 'schaarste', ECONOMIE: 'overaanbod', ZORG: 'evenwicht', ONDERWIJS: 'schaarste', RECHT: null },
      { TECHNIEK: 2.1, ECONOMIE: 0.5, ZORG: 1, ONDERWIJS: null, RECHT: null },
      false,
    )

    expect(uit.labels).toEqual(['Techniek', 'ZORG', 'Economie'])
    expect(uit.datasets.map(d => d.label)).toEqual(['Schaarste', 'Evenwicht', 'Overaanbod'])
    expect(uit.datasets[0].data).toEqual([2.1, null, null])
    expect(uit.datasets[1].data).toEqual([null, 1, null])
    expect(uit.datasets[2].data).toEqual([null, null, 0.5])
    expect(uit.zonderVerhouding).toEqual(['Onderwijs'])
  })

  it('zonder drempel geen lijnen', () => {
    expect(matchDrempels(undefined)).toEqual([])
    expect(matchDrempels(1.2)).toEqual([1 / 1.2, 1.2])
  })
})

describe('DREMPELLIJNEN', () => {
  it('tekent een stippellijn per waarde binnen de as, en geen buiten de as', () => {
    const lijnen = []
    const ctx = {
      save() {}, restore() {}, setLineDash() {}, beginPath() {}, stroke() {},
      moveTo(x, y) { lijnen.push([x, y]) }, lineTo() {},
    }
    const chart = {
      ctx,
      chartArea: { left: 100, right: 300, top: 10, bottom: 200 },
      scales: { x: { getPixelForValue: v => 100 + v * 100 } },
    }

    DREMPELLIJNEN.afterDatasetsDraw(chart, {}, { waarden: [0.5, 1.2, 5], kleur: '#6B7280' })

    expect(lijnen).toEqual([[150, 10], [220, 10]])
    expect(ctx.strokeStyle).toBe('#6B7280')
  })
})

// #952: één uitschieter (Tilburg University, Techniek: 52,15) maakte de rest onleesbaar, en een kleine sector kreeg een
// verhouding waar één diploma tientallen procenten verschil maakt.
describe('kap op de staaf en kleine sectoren (#952)', () => {
  it('kapt de staaf op MATCH_KAP en houdt de echte waarde in tooltip, tabel en noot', () => {
    const { score, verhouding } = sectoren(8)
    render({ matchScore: { ...score, TECHNIEK: 'schaarste' }, verhouding: { ...verhouding, TECHNIEK: 52.15 } })

    expect(MATCH_KAP).toBe(5)
    const { data, options } = getekend.at(-1)
    const schaarste = data.datasets.find(d => d.label === 'Schaarste')
    const i = data.labels.indexOf('Techniek')
    expect(schaarste.data[i]).toBe(MATCH_KAP)
    expect(schaarste.waarden[i]).toBe(52.15)
    expect(options.scales.x.max).toBe(MATCH_KAP)
    const tooltip = options.plugins.tooltip.callbacks.label({ dataset: schaarste, dataIndex: i, raw: MATCH_KAP })
    expect(tooltip).toBe(' Schaarste: 52,15 keer')
    expect(container.querySelector('.waarden-details').textContent).toContain('52,15')
    expect(container.querySelector('canvas').getAttribute('aria-label')).toContain('52,15')
    expect(container.textContent).toContain('Staaf afgekapt bij 5: Techniek (52,15).')
  })

  it('zonder uitschieter geen kap en geen noot', () => {
    const { score, verhouding } = sectoren(8)
    render({ matchScore: score, verhouding })

    expect(getekend.at(-1).options.scales.x.max).toBeUndefined()
    expect(container.textContent).not.toContain('afgekapt')
  })

  it('noemt elke sector zonder label met zijn reden uit de payload', () => {
    const { score, verhouding } = sectoren(8)
    const weggelaten = {
      RECHT: 'te weinig gediplomeerden: minder dan 30 per jaar',
      ONDERWIJS: 'geen beroepenclusters in de sectorindeling',
    }
    render({ matchScore: { ...score, RECHT: null, ONDERWIJS: null }, verhouding, weggelaten })

    expect(container.textContent).toContain('Niet getoond (te weinig gediplomeerden: minder dan 30 per jaar): Recht.')
    expect(container.textContent).toContain('Niet getoond (geen beroepenclusters in de sectorindeling): Onderwijs.')
  })

  it('de duiding zegt dat teller en noemer verschillende grootheden zijn, en noemt de drempel', () => {
    const { score, verhouding } = sectoren(3)
    render({ matchScore: score, verhouding, duiding: { ...DUIDING, min_gediplomeerden: 30 } })

    const duiding = container.querySelector('.db-match-duiding').textContent
    expect(duiding).toContain('Teller en noemer zijn dus verschillende grootheden')
    expect(duiding).toContain('minder dan 30 gediplomeerden per jaar krijgt geen label')
  })
})

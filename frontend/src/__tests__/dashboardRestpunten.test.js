// @vitest-environment jsdom
// #951: restpunten uit de visuele controle van de drie dashboards na 2.7.0. Elke liggende staaf noemt elke categorie
// (Chart.js sloeg elk tweede label over), lange woorden breken af op 390 px, sectoren heten bij hun naam, de
// ROA-prognose toont haar aantallen, het UWV-blok zegt "provincie", de rendementgrafiek heeft een korte legenda, en
// "ten minste" staat overal als hetzelfde label vóór het getal.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const getekend = []
vi.mock('react-chartjs-2', async () => {
  const { createElement: maak } = await import('react')
  const Canvas = ({ data, options, plugins, ...canvas }) => {
    getekend.push({ data, options, plugins })
    return maak('canvas', { role: 'img', ...canvas })
  }
  return { Line: Canvas, Bar: Canvas }
})

import { horizontalBarOpts, labelRegels, staafHoogte, LABEL_BREEDTE } from '../components/dashboards/shared/chart-opts'
import { PrognoseSection, UwvSection } from '../components/dashboards/shared/charts-arbeidsmarkt'
import { RendementSection } from '../components/dashboards/mijn-instelling/rendement-section'
import { DemografieKpis } from '../components/dashboards/shared/kpis'
import { fmtProcent } from '../components/dashboards/shared/getal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let container
let root

function render(element) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(element))
  return container
}

afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = container = undefined
  getekend.length = 0
})

describe('liggende staven noemen elke categorie (#951)', () => {
  it('zet autoSkip centraal uit, voor elke liggende staaf', () => {
    expect(horizontalBarOpts(false).scales.y.ticks.autoSkip).toBe(false)
    expect(horizontalBarOpts(true, '%').scales.y.ticks.autoSkip).toBe(false)
  })

  it('geeft elke categorie ruimte voor de regels van haar label', () => {
    const kort = ['Techniek', 'Economie', 'Recht']
    expect(staafHoogte(kort)).toBe(Math.max(160, 40 + 3 * 34))
    // Drie regels per label: 3 * 17 + 8 = 59 px per rij, meer dan de 34 van een kort label.
    const lang = ['Protestantse Theologische Universiteit', 'Techniek']
    expect(staafHoogte(lang, { minimum: 0 })).toBe(40 + 2 * 59)
    expect(staafHoogte(kort, { perRij: 72, minimum: 0, kader: 0 })).toBe(3 * 72)
  })

  it('breekt een woord dat langer is dan de as af, in plaats van het links te laten wegvallen', () => {
    const regels = labelRegels('Informatie- en communicatietechnologie')
    expect(regels.every(r => r.length <= LABEL_BREEDTE)).toBe(true)
    expect(regels).toEqual(['Informatie- en', 'communicatietechn-', 'ologie'])
  })
})

describe('ROA-prognose: de aantallen staan er (#951)', () => {
  it('toont baanopeningen en instroom als getal, de typering in woorden', () => {
    const prognose = {
      Mbo4: {
        'ITA toekomstige arbeidsmarktsituatie in 2030': 'redelijk',
        'verwachte baanopeningen tot 2030': 325800,
        'verwachte instroom van schoolverlaters tot 2030': 358700,
      },
    }
    const tekst = render(createElement(PrognoseSection, { data: { arbeidsmarkt_prognose: prognose } })).textContent

    expect(tekst).toContain('redelijk')
    expect(tekst).toContain('325.800')
    expect(tekst).toContain('358.700')
    const cellen = [...container.querySelectorAll('tbody td')].map(td => td.textContent)
    expect(cellen).not.toContain('—')
  })
})

describe('het UWV-blok gaat over de provincie (#951, F5)', () => {
  const vac = { totaal: 25225, peildatum: '2023-05-16', clusters: { Programmeurs: 900 }, gefilterd_op: ['GEDRAG_EN_MAATSCHAPPIJ', 'ECONOMIE'] }

  it('heet "in de provincie" en noemt de sectoren bij hun naam', () => {
    const tekst = render(createElement(UwvSection, { data: { vacatureaanbod: vac }, provincie: 'Utrecht', dark: false })).textContent

    expect(tekst).toContain('Vacatureaanbod in de provincie')
    expect(tekst).not.toContain('in de regio')
    expect(tekst).toContain('sectoren: Gedrag & Maatschappij, Economie')
    expect(tekst).not.toMatch(/GEDRAG_EN_MAATSCHAPPIJ|gedrag_en_maatschappij/)
  })

  it('zonder vacatures ook "in de provincie"', () => {
    const tekst = render(createElement(UwvSection, { data: {}, provincie: 'Utrecht', dark: false })).textContent
    expect(tekst).toContain('Vacatureaanbod in de provincie')
  })
})

describe('de rendementgrafiek heeft een korte legenda (#951)', () => {
  it('noemt in de legenda de groep, in de ondertitel het hele label', () => {
    const label = 'Provincie Noord-Brabant, 6 andere mbo-instellingen — te weinig mbo-instellingen in arbeidsmarktregio West-Brabant (1 andere)'
    const data = {
      gevonden: true, type: 'mbo', definitie: { naam: "Diploma's na 3 jaar per eerstejaars", termijn: 3, definitie: 'x' },
      pseudo_cohorten: [], rendement_per_jaar: { 2021: 0.9, 2022: 0.91 }, weggelaten: {},
      benchmark_label: label,
      benchmark_populatie: 'mbo-instellingen in provincie Noord-Brabant',
      benchmark_rendement: { 2021: 0.8, 2022: 0.82 }, benchmark_n_per_jaar: { 2021: 6, 2022: 6 },
      peers_rendement: {}, peers_weggelaten: {},
    }
    const tekst = render(createElement(RendementSection, { data, instelling: 'Curio', dark: false })).textContent

    const reeksen = getekend.at(-1).data.datasets.map(d => d.label)
    expect(reeksen).toEqual(['Curio', 'Gemiddelde mbo-instellingen in provincie Noord-Brabant'])
    expect(tekst).toContain(label)
  })
})

describe('"ten minste" en decimalen (#951)', () => {
  const basis = {
    instelling: 'Curio',
    lastInges: [2025, 15288], ingesDelta: 10, ingesEntries: [[2024, 15278], [2025, 15288]],
    totaalRegio: 72104, totaalRegioJaar: 2025, nPeers: 6, populatie: 'mbo-instellingen in provincie Noord-Brabant',
    regioType: 'provincie', perioden: { ingeschrevenen: 'schooljaar' },
  }

  it('het regiototaal noemt de eigen instelling en de andere, en is "ten minste" bij een lege cel', () => {
    render(createElement(DemografieKpis, { ...basis, bmOnderdrukt: { 2025: 1 } }))

    const tegels = [...container.querySelectorAll('.kpi-card')].map(k => k.textContent)
    const totaal = tegels.find(t => t.startsWith('Regio totaal'))
    expect(totaal).toContain('ten minste72.104')
    expect(totaal).toContain('Curio en 6 andere mbo-instellingen in provincie Noord-Brabant')
    expect(tegels.find(t => t.startsWith('Ingeschrevenen'))).not.toContain('ten minste')
  })

  it('de eigen ingeschrevenen krijgen hetzelfde label als in de kerncijfers', () => {
    render(createElement(DemografieKpis, { ...basis, onderdrukt: { 2025: 2 } }))

    expect(container.querySelectorAll('.kpi-ondergrens')).toHaveLength(2) // eigen en totaal
  })

  it('een aandeel heeft altijd één decimaal', () => {
    expect(fmtProcent(32)).toBe('32,0')
    expect(fmtProcent(67.24)).toBe('67,2')
    expect(fmtProcent(null)).toBe('—')
  })
})

// #905: de kleuren van de dashboards. Staven en lijnen halen 3:1 tegen de kaart (WCAG 1.4.11), tekst 4,5:1 (1.4.3), in
// beide thema's; er is één palet en een sector houdt in elke grafiek dezelfde kleur.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { contrast } from './helpers/pageRun'
import { CHART_COLORS, COLOR_EIGEN, COLOR_DIPLOM, COLOR_EERSTEJAARS } from '../constants'
import {
  benchmarkColor, oordeelKleur, sectorKleuren, SECTOR_LABELS, DAAL_KLEUR, GOED_KLEUR,
} from '../components/dashboards/shared/chart-opts'

const KAART = { licht: '#FFFFFF', donker: '#1A1F2E' } // --white in beide thema's (styles.css)

describe('palet (#905)', () => {
  it.each(CHART_COLORS)('%s haalt 3:1 tegen de kaart in beide thema\'s', kleur => {
    expect(contrast(kleur, KAART.licht)).toBeGreaterThanOrEqual(3)
    expect(contrast(kleur, KAART.donker)).toBeGreaterThanOrEqual(3)
  })

  it('haalt ook 3:1 voor de vaste kleuren', () => {
    for (const kleur of [COLOR_EIGEN, COLOR_DIPLOM, COLOR_EERSTEJAARS, DAAL_KLEUR, GOED_KLEUR]) {
      expect(contrast(kleur, KAART.licht), kleur).toBeGreaterThanOrEqual(3)
      expect(contrast(kleur, KAART.donker), kleur).toBeGreaterThanOrEqual(3)
    }
    expect(contrast(benchmarkColor(false), KAART.licht)).toBeGreaterThanOrEqual(3)
    expect(contrast(benchmarkColor(true), KAART.donker)).toBeGreaterThanOrEqual(3)
  })

  it('heeft verschillende kleuren voor alle sectoren', () => {
    expect(new Set(CHART_COLORS).size).toBe(CHART_COLORS.length)
    expect(CHART_COLORS.length).toBeGreaterThanOrEqual(Object.keys(SECTOR_LABELS).length)
  })
})

describe('sectorKleuren (#905)', () => {
  it('geeft een sector dezelfde kleur, in welke grafiek en op welke plek ook', () => {
    const a = sectorKleuren(['ECONOMIE', 'TECHNIEK', 'ONDERWIJS'])
    const b = sectorKleuren(['ONDERWIJS', 'Techniek'])
    expect(b.get('ONDERWIJS')).toBe(a.get('ONDERWIJS'))
    expect(b.get('Techniek')).toBe(a.get('TECHNIEK'))
  })

  it('geeft namen buiten de lijst vrije kleuren op alfabet, zonder dubbele', () => {
    const kleuren = sectorKleuren(['BOL voltijd', 'BBL', 'BOL deeltijd', 'ECONOMIE'])
    expect(new Set(kleuren.values()).size).toBe(4)
    expect(sectorKleuren(['BBL', 'BOL voltijd', 'BOL deeltijd']).get('BBL'))
      .toBe(sectorKleuren(['BOL deeltijd', 'BBL']).get('BBL'))
  })
})

describe('tekstkleuren (#905)', () => {
  it.each(['goed', 'gemiddeld', 'matig', 'slecht', 'neutraal'])('oordeel %s haalt 4,5:1 in beide thema\'s', oordeel => {
    expect(contrast(oordeelKleur(oordeel, false), KAART.licht)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(oordeelKleur(oordeel, true), KAART.donker)).toBeGreaterThanOrEqual(4.5)
  })

  it('geeft de trend in een kerncijfer 4,5:1 in beide thema\'s', () => {
    const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')
    const kleur = selector => css.match(new RegExp(`\\n${selector.replace(/\./g, '\\.')}\\s*{\\s*color:\\s*(#[0-9A-Fa-f]{6})`))?.[1]
    expect(contrast(kleur('.kpi-trend.up'), KAART.licht)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(kleur('.kpi-trend.down'), KAART.licht)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(kleur('html.dark .kpi-trend.up'), KAART.donker)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(kleur('html.dark .kpi-trend.down'), KAART.donker)).toBeGreaterThanOrEqual(4.5)
  })

  it('gebruikt in de dashboards geen hardgecodeerde lichte kleuren onder 3:1 meer', () => {
    const bronnen = ['shared/charts-markt.jsx', 'shared/charts-rendement.jsx', 'mijn-instelling/gender-section.jsx',
      'arbeidsmarkt-consolidated/index.jsx', 'shared/charts-arbeidsmarkt.jsx']
      .map(f => readFileSync(join(import.meta.dirname, '..', 'components', 'dashboards', f), 'utf8'))
    for (const zwak of ['#CBD5E1', '#E2E8F0', '#FEE2E2', '#D1FAE5', "'#94A3B8'"]) {
      expect(bronnen.filter(b => b.includes(zwak)), zwak).toEqual([])
    }
  })
})

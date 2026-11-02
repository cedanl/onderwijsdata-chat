import { describe, it, expect } from 'vitest'
import { leesFiguur } from '../figuurJson'

// #836: één helper voor het lezen van een figuur, voor PlotlyFigure, GeneratedDashboard en de dashboardkaart.
describe('leesFiguur', () => {
  it('parset een JSON-tekst', () => {
    expect(leesFiguur('{"data":[],"layout":{"title":"x"}}')).toEqual({ data: [], layout: { title: 'x' } })
  })

  it('geeft een al geparste figuur ongewijzigd terug', () => {
    const figuur = { data: [] }
    expect(leesFiguur(figuur)).toBe(figuur)
  })

  it('geeft null bij onleesbare JSON', () => {
    expect(leesFiguur('{kapot')).toBeNull()
  })
})

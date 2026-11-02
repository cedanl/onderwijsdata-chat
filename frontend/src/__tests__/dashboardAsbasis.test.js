import { describe, it, expect } from 'vitest'
import { AS_NIET_BIJ_NUL, afgekapteAs, tellingAs } from '../components/dashboards/shared/chart-opts'

// De asbasis van een lijn volgt de eenheid, zoals create_plot in tools/plot.py (#871): een telling begint op 0, een
// percentage mag afgekapt, maar dan staat dat op de as.
const AS = { grid: { color: '#eee' }, ticks: { color: '#666' } }

describe('tellingAs', () => {
  it('laat een as met aantallen op 0 beginnen en houdt de rest', () => {
    expect(tellingAs(AS)).toEqual({ ...AS, beginAtZero: true })
  })
})

describe('afgekapteAs', () => {
  it('zet op de as dat ze niet bij 0 begint als alle waarden erboven liggen', () => {
    const as = afgekapteAs(AS, [{ data: [62.5, 64.1, null] }, { data: [58.0, 60.2, 61] }], '#666')
    expect(as.title).toMatchObject({ display: true, text: AS_NIET_BIJ_NUL })
    expect(as.beginAtZero).toBeUndefined()
    expect(as.ticks).toBe(AS.ticks)
  })

  it('laat een as die door 0 loopt zoals ze is', () => {
    expect(afgekapteAs(AS, [{ data: [0, 12, 30] }], '#666')).toBe(AS)
    expect(afgekapteAs(AS, [{ data: [-3, 4] }], '#666')).toBe(AS)
    expect(afgekapteAs(AS, [{ data: [null] }], '#666')).toBe(AS)
  })

  it('telt alleen de reeksen die de grafiek bij het openen toont', () => {
    const as = afgekapteAs(AS, [{ data: [55, 60] }, { data: [0, 2], hidden: true }], '#666')
    expect(as.title?.text).toBe(AS_NIET_BIJ_NUL)
  })
})

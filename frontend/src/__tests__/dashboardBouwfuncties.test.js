// #907: de build*Data-functies van de dashboards die nog geen test hadden. Elk zet een payload van de server om in de
// reeksen van één grafiek: welke jaren of instellingen meedoen, welk getal er staat, en wanneer er geen grafiek is.
// (buildRendementVergelijkingData staat hier niet: #927 werkt die om.)
import { describe, it, expect } from 'vitest'
import { buildMarktaandeelTrendData, buildInstroomRatioData, buildMarktaandeelData } from '../components/dashboards/shared/charts-markt'
import { buildTrendLineData, buildPeerGenderData } from '../components/dashboards/mijn-instelling/gender-section'
import { buildEigenSectorenTrendData } from '../components/dashboards/nationaal/index'
import { benchmarkColor } from '../components/dashboards/shared/chart-opts'
import { COLOR_EIGEN, COLOR_DIPLOM } from '../constants'

describe('buildMarktaandeelTrendData', () => {
  it('geeft per jaar het eigen aandeel in eigen plus regio, alleen voor jaren met een regiototaal', () => {
    const data = buildMarktaandeelTrendData({
      ingeschrevenen: { 2023: 100, 2024: 120, 2025: 130 },
      benchmark: { totaal_ingeschrevenen: { 2023: 300, 2024: 280 } },
    })
    expect(data.labels).toEqual(['2023', '2024'])
    expect(data.datasets[0].data).toEqual([25, 30])
  })

  it('tekent niets met minder dan twee jaren of zonder regiototaal', () => {
    expect(buildMarktaandeelTrendData({ ingeschrevenen: { 2025: 1 }, benchmark: { totaal_ingeschrevenen: { 2025: 9 } } })).toBeNull()
    expect(buildMarktaandeelTrendData({ ingeschrevenen: { 2024: 1, 2025: 1 } })).toBeNull()
  })
})

describe('buildInstroomRatioData', () => {
  it('geeft eerstejaars als % van de ingeschrevenen van hetzelfde jaar', () => {
    const data = buildInstroomRatioData({ eerstejaars: { 2023: 30, 2024: 40, 2025: 5 }, ingeschrevenen: { 2023: 100, 2024: 160 } })
    expect(data.labels).toEqual(['2023', '2024'])
    expect(data.datasets[0].data).toEqual([30, 25])
  })

  it('laat een jaar zonder ingeschrevenen een gat, en tekent niets met één jaar', () => {
    expect(buildInstroomRatioData({ eerstejaars: { 2023: 30, 2024: 40 }, ingeschrevenen: { 2023: 0, 2024: 80 } }).datasets[0].data)
      .toEqual([null, 50])
    expect(buildInstroomRatioData({ eerstejaars: { 2024: 40 }, ingeschrevenen: { 2024: 80 } })).toBeNull()
  })
})

describe('buildMarktaandeelData', () => {
  const data = {
    laatste_jaar: 2025,
    ingeschrevenen: { 2025: 500 },
    benchmark: { peers: { ingeschrevenen: { 'Hogeschool A': { 2025: 800 }, 'Hogeschool B': { 2025: 200 } } } },
  }

  it('zet de eigen instelling tussen de peers, aflopend, in de eigen kleur', () => {
    const uit = buildMarktaandeelData(data, 'Hogeschool Utrecht', false)
    expect(uit.labels).toEqual(['Hogeschool A', 'Hogeschool Utrecht', 'Hogeschool B'])
    expect(uit.datasets[0].data).toEqual([800, 500, 200])
    expect(uit.datasets[0].backgroundColor).toEqual([benchmarkColor(false), COLOR_EIGEN, benchmarkColor(false)])
  })

  it('tekent niets zonder peers', () => {
    expect(buildMarktaandeelData({ ...data, benchmark: { peers: { ingeschrevenen: {} } } }, 'Hogeschool Utrecht', false)).toBeNull()
  })
})

describe('buildTrendLineData (aandeel vrouw)', () => {
  it('geeft het aandeel vrouw per jaar op volgorde, zonder jaren waarin vrouw of man ontbreekt', () => {
    const data = buildTrendLineData({
      2024: { VROUW: 55, MAN: 45 },
      2022: { VROUW: null, MAN: 40 },
      2023: { VROUW: 60, MAN: 40 },
    })
    expect(data.labels).toEqual(['2023', '2024'])
    expect(data.datasets[0].data).toEqual([60, 55])
  })

  it('tekent niets met één bruikbaar jaar', () => {
    expect(buildTrendLineData({ 2023: { VROUW: 60, MAN: 40 }, 2024: { MAN: 45 } })).toBeNull()
  })
})

describe('buildPeerGenderData', () => {
  it('zet de eigen instelling tussen de peers met een aandeel, aflopend', () => {
    const data = buildPeerGenderData(
      { 'Hogeschool A': { VROUW: 30, MAN: 70 }, 'Hogeschool B': { VROUW: null, MAN: 5 } },
      'Hogeschool Utrecht', 60, false,
    )
    expect(data.labels).toEqual(['Hogeschool Utrecht', 'Hogeschool A'])
    expect(data.datasets[0].data).toEqual([60, 30])
    expect(data.datasets[0].backgroundColor).toEqual([COLOR_DIPLOM, benchmarkColor(false)])
  })

  it('tekent niets als alleen de eigen instelling een aandeel heeft', () => {
    expect(buildPeerGenderData({ 'Hogeschool B': { MAN: 5 } }, 'Hogeschool Utrecht', 60, false)).toBeNull()
  })
})

describe('buildEigenSectorenTrendData (Landelijk)', () => {
  it('geeft per sector een lijn zonder vlakvulling, met een gat voor een jaar zonder waarde', () => {
    const data = buildEigenSectorenTrendData({ ECONOMIE: { 2023: 100, 2025: 120 }, TECHNIEK: { 2023: 50, 2024: 55, 2025: 60 } })
    expect(data.labels).toEqual(['2023', '2024', '2025'])
    expect(data.datasets.map(d => d.label)).toEqual(['Economie', 'Techniek'])
    expect(data.datasets[0].data).toEqual([100, null, 120])
    for (const d of data.datasets) {
      expect(d.fill).toBe(false)
      expect(d.backgroundColor).toBe(`${d.borderColor}33`)
    }
  })

  it('tekent niets met één jaar', () => {
    expect(buildEigenSectorenTrendData({ ECONOMIE: { 2025: 120 } })).toBeNull()
  })
})

import { describe, it, expect } from 'vitest'
import { buildSupplyDemandData } from '../components/dashboards/shared/chart-builders'

// The backend counts a UWV cluster shared by several sectors pro rata (#455); the chart plots
// that count and no longer re-sums the clusters per sector.
const GEDIPLOMEERDEN = { TECHNIEK: 50, ECONOMIE: 50 }
const VACATURES_PER_SECTOR = { TECHNIEK: 1500, ECONOMIE: 1300 }

describe('buildSupplyDemandData', () => {
  it('plots the weighted vacancies per sector, not the summed clusters', () => {
    const data = buildSupplyDemandData(GEDIPLOMEERDEN, VACATURES_PER_SECTOR)
    const [diplomas, vacatures] = data.datasets

    expect(data.labels).toEqual(['Techniek', 'Economie'])
    expect(diplomas.data).toEqual([50, 50])
    expect(vacatures.data).toEqual([1500, 1300])
    // Chauffeurs (2000) summed into both sectors gave 2500 and 2300 of 2800 vacancies.
    expect(vacatures.data).not.toEqual([2500, 2300])
  })

  it('plots 0 for a sector without a vacancy count', () => {
    const data = buildSupplyDemandData({ TECHNIEK: 50, ONDERWIJS: 10 }, { TECHNIEK: 1500 })

    expect(data.datasets[1].data).toEqual([1500, 0])
  })

  it('returns null without diplomas or vacancy counts', () => {
    expect(buildSupplyDemandData(undefined, VACATURES_PER_SECTOR)).toBeNull()
    expect(buildSupplyDemandData(GEDIPLOMEERDEN, undefined)).toBeNull()
    expect(buildSupplyDemandData({}, VACATURES_PER_SECTOR)).toBeNull()
  })
})

// #795: een dashboard heet in de feedbackteksten geen rapport; een rapport blijft rapport.
import { describe, it, expect } from 'vitest'
import { metWoord, rapportWoord } from '../rapportWoord'

describe('rapportWoord', () => {
  it.each([
    [{ type: 'report' }, 'rapport'],
    [{ type: 'dashboard' }, 'dashboard'],
    [{ htmlContent: '<p>x</p>' }, 'rapport'],
    [{ dashboardSpec: {} }, 'dashboard'],
  ])('kiest het woord voor %j', (workbook, verwacht) => {
    expect(rapportWoord(workbook)).toBe(verwacht)
  })
})

describe('metWoord', () => {
  it('laat een rapport ongemoeid', () => {
    expect(metWoord('Hoe nuttig was dit rapport voor je?', 'rapport')).toBe('Hoe nuttig was dit rapport voor je?')
  })

  it('zet enkelvoud en meervoud om voor een dashboard', () => {
    expect(metWoord('Mist er iets in dit rapport?', 'dashboard')).toBe('Mist er iets in dit dashboard?')
    expect(metWoord('de rapporten te verbeteren', 'dashboard')).toBe('de dashboards te verbeteren')
    expect(metWoord('Over dit rapport', 'dashboard')).toBe('Over dit dashboard')
  })

  it('laat tekst zonder het woord staan', () => {
    expect(metWoord('Over jouw instelling', 'dashboard')).toBe('Over jouw instelling')
  })
})

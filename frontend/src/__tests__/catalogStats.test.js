import { describe, it, expect } from 'vitest'
import { heroStats } from '../catalogStats'

// The source count comes from bronnenLijst.js (aantalBronnen, #1010); heroStats only counts the datasets.
describe('heroStats', () => {
  it('counts the datasets the chat can search', () => {
    expect(heroStats({ CBS: 266, DUO: 56, RIO: 14 })).toEqual({ datasets: '336' })
  })

  it('formats a large count the Dutch way', () => {
    expect(heroStats({ CBS: 1200, DUO: 56 })).toEqual({ datasets: '1.256' })
  })

  it('shows a placeholder until the counts have loaded', () => {
    expect(heroStats({})).toEqual({ datasets: '–' })
  })
})

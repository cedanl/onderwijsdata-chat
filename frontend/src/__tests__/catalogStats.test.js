import { describe, it, expect } from 'vitest'
import { heroStats } from '../catalogStats'

describe('heroStats', () => {
  it('counts the sources the chat can query and their datasets', () => {
    expect(heroStats({ CBS: 266, DUO: 56, RIO: 14 })).toEqual({ bronnen: 3, datasets: '336' })
  })

  it('shows a placeholder until the counts have loaded', () => {
    expect(heroStats({})).toEqual({ bronnen: '–', datasets: '–' })
  })
})

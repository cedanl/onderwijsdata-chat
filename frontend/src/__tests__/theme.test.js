// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { applyMode } from '../theme'

function osPrefersDark(dark) {
  window.matchMedia = q => ({ matches: dark && q.includes('dark'), media: q })
}

const html = () => document.documentElement.classList

describe('applyMode', () => {
  beforeEach(() => { document.documentElement.className = '' })

  it('marks an explicit light choice so a dark OS cannot override it', () => {
    osPrefersDark(true)
    applyMode('light')
    expect(html().contains('light')).toBe(true)
    expect(html().contains('dark')).toBe(false)
  })

  it('applies dark on a light OS when chosen', () => {
    osPrefersDark(false)
    applyMode('dark')
    expect(html().contains('dark')).toBe(true)
    expect(html().contains('light')).toBe(false)
  })

  it('follows the OS in system mode', () => {
    osPrefersDark(true)
    applyMode('system')
    expect(html().contains('dark')).toBe(true)
    osPrefersDark(false)
    applyMode('system')
    expect(html().contains('dark')).toBe(false)
    expect(html().contains('light')).toBe(false)
  })

  it('switches cleanly from light to dark', () => {
    osPrefersDark(false)
    applyMode('light')
    applyMode('dark')
    expect([...html()]).toEqual(['dark'])
  })
})

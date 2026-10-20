// @vitest-environment jsdom
// #635: wat de server van het open gesprek heeft, en uitloggen dat op een lopende opslag wacht.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { isOpgeslagen, noteerOpgeslagen, vingerafdruk, volgOpslag, wachtOpOpslag } from '../gesprekOpslag'

beforeEach(() => localStorage.clear())

describe('de vingerafdruk van de laatste geslaagde opslag', () => {
  it('herkent hetzelfde gesprek en ziet elke wijziging', () => {
    noteerOpgeslagen('c1', '[{"content":"a"}]')
    expect(isOpgeslagen('c1', '[{"content":"a"}]')).toBe(true)
    expect(isOpgeslagen('c1', '[{"content":"b"}]')).toBe(false)
    expect(isOpgeslagen('c2', '[{"content":"a"}]')).toBe(false)
  })

  it('bewaart alleen het id en een hash, geen inhoud', () => {
    noteerOpgeslagen('c1', '[{"content":"Hoeveel studenten in Utrecht?"}]')
    expect(Object.values(localStorage).join('')).not.toContain('Utrecht')
    expect(vingerafdruk('x'.repeat(400000))).toMatch(/^[0-9a-z]+$/)
  })

  it('weet niets zonder afdruk of met een onleesbare', () => {
    expect(isOpgeslagen('c1', '[]')).toBe(false)
    localStorage.setItem('openEDUdata_opgeslagen', '{kapot')
    expect(isOpgeslagen('c1', '[]')).toBe(false)
  })
})

describe('wachten op een lopende opslag', () => {
  it('is meteen klaar als er niets loopt', async () => {
    await expect(wachtOpOpslag()).resolves.toBeUndefined()
  })

  it('wacht tot de opslag klaar is, ook als die mislukt', async () => {
    let klaar
    volgOpslag(new Promise((_, nee) => { klaar = nee })).catch(() => {})
    let gewacht = false
    const wachten = wachtOpOpslag().then(() => { gewacht = true })
    await Promise.resolve()
    expect(gewacht).toBe(false)
    klaar(new Error('offline'))
    await wachten
    expect(gewacht).toBe(true)
  })

  it('wacht niet langer dan de grens', async () => {
    vi.useFakeTimers()
    volgOpslag(new Promise(() => {}))
    const wachten = wachtOpOpslag(5000)
    await vi.advanceTimersByTimeAsync(5000)
    await expect(wachten).resolves.toBeUndefined()
    vi.useRealTimers()
  })
})

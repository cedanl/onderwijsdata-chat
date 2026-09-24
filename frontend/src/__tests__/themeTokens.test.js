import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')

describe('theme tokens', () => {
  it('keeps --on-color white in the dark theme', () => {
    expect([...css.matchAll(/--on-color\s*:\s*([^;]+);/g)].map(m => m[1].trim())).toEqual(['#FFFFFF'])
  })

  // The dark theme turns --white into a dark surface colour; as text colour it is only right
  // where the background flips along with it.
  it('uses --white as text colour only on surfaces that flip with it', () => {
    const rules = [...css.matchAll(/([^{}]+)\{[^}]*[^-]color:\s*var\(--white\)/g)].map(m => m[1].trim())
    expect(rules).toEqual(['.toast.info'])
  })
})

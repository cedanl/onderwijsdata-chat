import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join(__dirname, '..')
const css = readFileSync(join(SRC, 'styles.css'), 'utf8')

function sources(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    if (e.name === '__tests__') return []
    const path = join(dir, e.name)
    return e.isDirectory() ? sources(path) : /\.(css|jsx?)$/.test(e.name) ? [path] : []
  })
}

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

  // Both stay below 4.5:1 as text (gray-400 on white, blue-600 on the dark background).
  it('uses the text tokens instead of --gray-400 and --blue-600 for text', () => {
    const offenders = sources(SRC).flatMap(file =>
      [...readFileSync(file, 'utf8').matchAll(/(?<![\w-])color:\s*'?var\(--(gray-400|blue-600)\)/g)]
        .map(m => `${file.split('/src/')[1]}: ${m[1]}`))
    expect(offenders).toEqual([])
  })
})

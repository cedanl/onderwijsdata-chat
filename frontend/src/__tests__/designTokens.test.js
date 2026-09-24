import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join(__dirname, '..')

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    if (entry.name === '__tests__') return []
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.(css|jsx?)$/.test(entry.name) ? [path] : []
  })
}

describe('design tokens', () => {
  // An undefined custom property makes the whole declaration invalid, so a focus ring or
  // border silently disappears instead of failing loudly.
  it('defines every token that is used without a fallback', () => {
    const css = readFileSync(join(SRC, 'styles.css'), 'utf8')
    const defined = new Set([...css.matchAll(/(--[\w-]+)\s*:/g)].map(m => m[1]))
    const missing = new Set()
    for (const file of sourceFiles(SRC)) {
      for (const [, name, fallback] of readFileSync(file, 'utf8').matchAll(/var\((--[\w-]+)\s*(,)?/g)) {
        if (!fallback && !defined.has(name)) missing.add(name)
      }
    }
    expect([...missing]).toEqual([])
  })
})

// #564: jsdom does no layout or colour, so this pins the CSS agreement for the search on /rapporten.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
const ruleBody = selector => css.match(new RegExp(`(?:^|})\\s*${selector.replace('.', '\\.')}\\s*{([^}]*)}`))?.[1]

describe('"Wis zoekopdracht" button border', () => {
  // Same token as the search field: the edge keeps 3:1 against the page in both themes (WCAG 1.4.11).
  it('uses --gray-500, not the too light --gray-200', () => {
    const rule = ruleBody('.wb-gallery-clear-btn')
    expect(rule).toBeDefined()
    expect(rule).toContain('border: 1px solid var(--gray-500)')
    expect(rule).not.toContain('var(--gray-200)')
  })
})

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')

function rulesFor(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return [...css.matchAll(new RegExp(`(?:^|[},])\\s*${escaped}\\s*\\{([^}]*)\\}`, 'gm'))].map(m => m[1])
}

// CH-36: the report cancel button was about 22px high on desktop; a tap target is 44px.
describe('report cancel button', () => {
  it('is at least 44px high outside any media query', () => {
    const [base] = rulesFor('.report-cancel-btn')
    expect(base).toMatch(/min-height:\s*44px/)
  })

  it('has no other rule that lowers its height', () => {
    const declarations = rulesFor('.report-cancel-btn').join(';')
    const heights = [...declarations.matchAll(/(?:^|[;\s])(?:min-)?height:\s*([\d.]+)px/g)].map(m => Number(m[1]))
    expect(heights.every(h => h >= 44)).toBe(true)
  })
})

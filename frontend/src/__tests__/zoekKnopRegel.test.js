// #602: on a window of about 1025px the search button shrank and "Ctrl K" broke over two lines. jsdom does no
// layout, so this pins the CSS agreement: the button does not wrap and does not shrink.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
const body = css.match(/\n\.navbar-zoek-btn\s*\{([^}]*)\}/)?.[1] ?? ''

describe('search button in the navbar', () => {
  it('keeps the label and the shortcut on one line', () => {
    expect(body).toMatch(/white-space:\s*nowrap/)
  })
  it('does not shrink when the bar is tight', () => {
    expect(body).toMatch(/flex-shrink:\s*0/)
  })
})

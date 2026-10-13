import { describe, it, expect } from 'vitest'
import { figureHeight, figureHeightOfJson, legendBelow, legendRepeatsAxis } from '../figureLayout'

// Horizontal bars grow with the number of categories; a fixed 340 px squashed 18 of them.
describe('figureHeight', () => {
  it('uses the height the server gave the chart', () => {
    expect(figureHeight({ height: 526 }, 340)).toBe(526)
  })

  it('falls back on the base height without one', () => {
    expect(figureHeight({}, 340)).toBe(340)
    expect(figureHeight(undefined, 360)).toBe(360)
    expect(figureHeight({ height: 0 }, 340)).toBe(340)
    expect(figureHeight({ height: '600' }, 340)).toBe(340)
  })

  it('reads the figure JSON of a report, and falls back on invalid JSON', () => {
    expect(figureHeightOfJson(JSON.stringify({ data: [], layout: { height: 700 } }), 360)).toBe(700)
    expect(figureHeightOfJson('{niet json', 360)).toBe(360)
  })
})

describe('legendBelow', () => {
  it('puts a legend without a place of its own under the chart, keeping its title and colours', () => {
    const legend = legendBelow({ title: { text: 'Instelling' }, bgcolor: '#fff' })
    expect(legend).toMatchObject({ orientation: 'h', yref: 'container', y: 0, yanchor: 'bottom' })
    expect(legend.title.text).toBe('Instelling')
    expect(legendBelow(undefined)).toMatchObject({ orientation: 'h', y: 0 })
  })

  it('leaves a legend that has a place where it is', () => {
    const placed = { x: 0.02, y: 0.98 }
    expect(legendBelow(placed)).toBe(placed)
    expect(legendBelow({ orientation: 'v' })).toEqual({ orientation: 'v' })
  })
})

describe('legendRepeatsAxis', () => {
  const bar = (name, x = name) => ({ type: 'bar', name, x: [x], y: [1] })

  it('recognises a series per bar, named after its own bar', () => {
    expect(legendRepeatsAxis([bar('UvA'), bar('VU')])).toBe(true)
  })

  it('keeps the legend of real groups', () => {
    expect(legendRepeatsAxis([bar('Man', 'UvA'), bar('Vrouw', 'UvA')])).toBe(false)
    expect(legendRepeatsAxis([{ name: 'hbo', x: ['2023', '2024'], y: [1, 2] }, { name: 'wo', x: ['2023', '2024'], y: [3, 4] }])).toBe(false)
    expect(legendRepeatsAxis([bar('UvA')])).toBe(false)
    expect(legendRepeatsAxis(undefined)).toBe(false)
  })
})

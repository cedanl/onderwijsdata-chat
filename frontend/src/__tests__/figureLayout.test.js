import { describe, it, expect } from 'vitest'
import { chatFigureLayout, figureHeight, figureHeightOfJson, legendBelow, legendRepeatsAxis } from '../figureLayout'
import { figureCsvFilename } from '../figureCsv'

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

// #587: the chat showed a long title on one line, and on a phone its end fell off the figure.
describe('chatFigureLayout', () => {
  const ISSUE = 'Mbo-studenten totaal (incl. extranei), 2020/2021 – 2024/2025'
  const LINE = 16 * 1.3
  const title = { text: ISSUE, font: { size: 16, color: '#222' } }
  const note = { text: 'De aantallen zijn door CBS afgerond<br>op 10-tallen.', font: { size: 11, color: '#666' } }
  const withNote = { ...title, yref: 'container', yanchor: 'top', y: 0.98, subtitle: note }
  const bar = layout => ({ data: [{ type: 'bar', x: ['2020/2021'], y: [1] }], layout })
  const map = layout => ({ data: [{ type: 'choroplethmap', locations: ['PV20'], z: [1] }], layout })
  const lines = layout => layout.title.text.split('<br>').length

  it('leaves title and top margin alone while the width is unknown', () => {
    const layout = chatFigureLayout(bar({ title, margin: { t: 60 } }), false, 0)
    expect(layout.title).toEqual(title)
    expect(layout.margin).toEqual({ l: 48, r: 24, t: 32, b: 40 })
  })

  it('breaks a long title on a phone and raises the top margin by the extra lines', () => {
    const layout = chatFigureLayout(bar({ title }), false, 336)
    expect(lines(layout)).toBeGreaterThan(1)
    expect(layout.title.text.replaceAll('<br>', ' ')).toBe(ISSUE)
    expect(layout.margin.t).toBeCloseTo(32 + (lines(layout) - 1) * LINE)
    expect(layout.title.font).toEqual(title.font)
  })

  it('keeps a title that fits on one line, and exactly the old top margin', () => {
    const layout = chatFigureLayout(bar({ title }), false, 1280)
    expect(layout.title.text).toBe(ISSUE)
    expect(layout.margin.t).toBe(32)
    expect(chatFigureLayout(bar({ title: withNote, margin: { t: 100 } }), false, 1280).margin.t).toBe(100)
  })

  it('adds only the extra lines to the margin the server gave a chart with a note', () => {
    const layout = chatFigureLayout(bar({ title: withNote, margin: { t: 100 } }), false, 336)
    expect(layout.margin.t).toBeCloseTo(100 + (lines(layout) - 1) * LINE)
    expect(layout.title.subtitle).toEqual(note)
    expect(layout.title).toMatchObject({ yref: 'container', yanchor: 'top', y: 0.98 })
  })

  it('gives a map the same title treatment', () => {
    const layout = chatFigureLayout(map({ title }), false, 336)
    expect(lines(layout)).toBeGreaterThan(1)
    expect(layout.margin).toEqual({ l: 0, r: 0, t: 32 + (lines(layout) - 1) * LINE, b: 0 })
  })

  it('accepts a title given as a string', () => {
    const layout = chatFigureLayout(bar({ title: ISSUE }), false, 336)
    expect(lines(layout)).toBeGreaterThan(1)
    expect(chatFigureLayout(bar({ title: 'Kort' }), false, 336).title).toBe('Kort')
  })

  it('leaves the figure alone, so the CSV file name keeps the unbroken title', () => {
    const figure = bar({ title: withNote, margin: { t: 100 } })
    const before = structuredClone(figure)
    chatFigureLayout(figure, true, 336)
    expect(figure).toEqual(before)
    expect(figureCsvFilename(figure)).not.toContain('br')
  })

  it('gives the title and note light colours in the dark theme, and keeps them in the light one', () => {
    const dark = chatFigureLayout(bar({ title: withNote, margin: { t: 100 } }), true, 336)
    expect(dark.title.font).toEqual({ size: 16, color: '#F9FAFB' })
    expect(dark.title.subtitle.font).toEqual({ size: 11, color: '#9CA3AF' })
    expect(dark.paper_bgcolor).toBe('#1E293B')
    const light = chatFigureLayout(bar({ title: withNote, margin: { t: 100 } }), false, 336)
    expect(light.title.font.color).toBe('#222')
    expect(light.title.subtitle.font.color).toBe('#666')
  })

  it('adds no title to a figure without one', () => {
    expect(chatFigureLayout(bar({}), true, 336)).not.toHaveProperty('title')
    expect(chatFigureLayout({ data: [] }, false, 336).margin.t).toBe(32)
  })
})

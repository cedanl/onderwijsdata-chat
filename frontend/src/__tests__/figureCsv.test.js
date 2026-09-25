import { describe, it, expect } from 'vitest'
import { figureToCsv } from '../figureCsv'

const lines = csv => csv.split('\n')

describe('figureToCsv', () => {
  it('uses the column names from the figure metadata', () => {
    const figure = {
      data: [{ x: [2021, 2022], y: [28355, 27904] }],
      layout: { meta: { x: 'STUDIEJAAR', y: 'AANTAL_INGESCHREVENEN' } },
    }
    expect(lines(figureToCsv(figure))).toEqual([
      'STUDIEJAAR;AANTAL_INGESCHREVENEN', '2021;28355', '2022;27904',
    ])
  })

  it('falls back to axis titles when there is no metadata', () => {
    const figure = {
      data: [{ x: ['HU'], y: [1] }],
      layout: { xaxis: { title: { text: 'INSTELLING' } }, yaxis: { title: { text: 'AANTAL' } } },
    }
    expect(lines(figureToCsv(figure))[0]).toBe('INSTELLING;AANTAL')
  })

  it('names one column per series when the chart is split by group', () => {
    const figure = {
      data: [{ name: 'VT', x: [2021], y: [10] }, { name: 'DT', x: [2021], y: [3] }],
      layout: { meta: { x: 'STUDIEJAAR', y: 'AANTAL' } },
    }
    expect(lines(figureToCsv(figure))).toEqual(['STUDIEJAAR;VT;DT', '2021;10;3'])
  })

  it('puts each value on the row of its own x when series have different x values', () => {
    // Live-audit 6: two traces, one per year, came out as one row "2024/'25;378490;367960".
    const figure = {
      data: [
        { name: '2024/25', x: ["2024/'25"], y: [378490] },
        { name: '2025/26', x: ["2025/'26"], y: [367960] },
      ],
      layout: { meta: { x: 'Perioden', y: 'Ingeschrevenen' } },
    }
    expect(lines(figureToCsv(figure))).toEqual([
      'Perioden;2024/25;2025/26', "2024/'25;378490;", "2025/'26;;367960",
    ])
  })

  it('quotes values that contain the separator or quotes', () => {
    const figure = {
      data: [{ x: ['Hogeschool; Utrecht', 'De "Haagse"'], y: [1, 2] }],
      layout: { meta: { x: 'INSTELLING', y: 'AANTAL' } },
    }
    expect(lines(figureToCsv(figure)).slice(1)).toEqual(['"Hogeschool; Utrecht";1', '"De ""Haagse""";2'])
  })

  it('returns null for a figure without data', () => {
    expect(figureToCsv({ data: [] })).toBeNull()
    expect(figureToCsv({ data: [{ x: [] }] })).toBeNull()
  })
})

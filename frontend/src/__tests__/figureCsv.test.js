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

  it('exports the tool rows from the figure metadata, all columns and every row', () => {
    // #183: a bar chart with a repeated x label. The rows behind the chart are
    // the export; nothing is reconstructed from the drawn traces.
    const figure = {
      data: [{ x: ['economie', 'economie', 'recht'], y: [137, 2351, null] }],
      layout: {
        meta: {
          x: 'SUBONDERDEEL', y: 'AANTAL',
          data: [
            { SUBONDERDEEL: 'economie', AANTAL: 137, STUDIEJAAR: 2021 },
            { SUBONDERDEEL: 'economie', AANTAL: 2351, STUDIEJAAR: 2021 },
            { SUBONDERDEEL: 'recht', AANTAL: null, STUDIEJAAR: 2021 },
          ],
        },
      },
    }
    expect(lines(figureToCsv(figure))).toEqual([
      'SUBONDERDEEL;AANTAL;STUDIEJAAR', 'economie;137;2021', 'economie;2351;2021', 'recht;;2021',
    ])
  })

  it('keeps every point of a trace whose x labels repeat (live-audit 7a: 14 points, sum 5.943)', () => {
    const xs = ['n.v.t. (economie)', 'n.v.t. (economie)', 'n.v.t. (economie)', 'gedrag', 'gedrag',
      'techniek', 'techniek', 'techniek', 'zorg', 'zorg', 'onderwijs', 'onderwijs', 'taal', 'taal']
    const ys = [137, 66, 2351, 400, 300, 500, 250, 150, 700, 400, 300, 200, 189, null]
    const figure = { data: [{ x: xs, y: ys }], layout: { meta: { x: 'SUBONDERDEEL', y: 'AANTAL' } } }

    const rows = lines(figureToCsv(figure)).slice(1).map(r => r.split(';'))
    expect(rows).toHaveLength(14)
    expect(rows.reduce((sum, r) => sum + Number(r[1]), 0)).toBe(5943)
    expect(rows[13]).toEqual(['taal', ''])
  })

  it('writes one row per point, with the series, when repeated x labels meet several series', () => {
    const figure = {
      data: [{ name: 'VT', x: ['a', 'a'], y: [1, 2] }, { name: 'DT', x: ['a'], y: [3] }],
      layout: { meta: { x: 'SUB', y: 'AANTAL' } },
    }
    expect(lines(figureToCsv(figure))).toEqual(['reeks;SUB;AANTAL', 'VT;a;1', 'VT;a;2', 'DT;a;3'])
  })

  it('exports a map from its rows, although its traces have no x values', () => {
    const figure = {
      data: [{ type: 'choroplethmap', locations: ['PV20'], z: [12] }],
      layout: { meta: { type: 'choropleth', data: [{ RegioS: 'PV20', AANTAL: 12 }] } },
    }
    expect(lines(figureToCsv(figure))).toEqual(['RegioS;AANTAL', 'PV20;12'])
  })

  it('returns null for a figure without data', () => {
    expect(figureToCsv({ data: [] })).toBeNull()
    expect(figureToCsv({ data: [{ x: [] }] })).toBeNull()
  })
})

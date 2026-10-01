import { describe, it, expect } from 'vitest'
import { figureToCsv, figureCsvProblem } from '../figureCsv'

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

  describe('binary Plotly arrays (#217)', () => {
    // numpy int16 [24169, 24740] / int16 [1, -2, 300] as plotly.py serialises them
    const i2 = (...n) => ({ dtype: 'i2', bdata: btoa(String.fromCharCode(...new Uint8Array(new Int16Array(n).buffer))) })
    const f8 = (...n) => ({ dtype: 'f8', bdata: btoa(String.fromCharCode(...new Uint8Array(new Float64Array(n).buffer))) })

    it('decodes a typed y array instead of exporting empty cells', () => {
      const figure = { data: [{ type: 'bar', x: ['Avans', 'Fontys'], y: i2(24169, 24740) }], layout: { meta: { x: 'categorie', y: 'Aantal' } } }
      expect(lines(figureToCsv({ ...figure, layout: {} }))).toEqual(['categorie;waarde', 'Avans;24169', 'Fontys;24740'])
    })

    it('decodes typed x and floats, and keeps null gaps', () => {
      const figure = { data: [{ x: i2(2021, 2022, 2023), y: [1.5, null, 3] }] }
      expect(lines(figureToCsv(figure))).toEqual(['categorie;waarde', '2021;1.5', '2022;', '2023;3'])
      expect(lines(figureToCsv({ data: [{ x: ['a'], y: f8(0.25) }] }))).toEqual(['categorie;waarde', 'a;0.25'])
    })

    it('decodes grouped traces', () => {
      const figure = { data: [{ name: 'VT', x: ['a', 'b'], y: i2(1, 2) }, { name: 'DT', x: ['a', 'b'], y: i2(3, 4) }], layout: { meta: { x: 'SUB', y: 'AANTAL' } } }
      expect(lines(figureToCsv(figure))).toEqual(['SUB;VT;DT', 'a;1;3', 'b;2;4'])
    })

    it('treats undecodable binary as a problem, not as an empty export', () => {
      const figure = { data: [{ x: ['a'], y: { dtype: 'zz', bdata: 'AA==' } }] }
      expect(figureToCsv(figure)).toBeNull()
      expect(figureCsvProblem(figure)).toMatch(/ontbreken/)
    })
  })

  describe('validation (#217)', () => {
    const problem = trace => figureCsvProblem({ data: [trace] })

    it('refuses x and y of different length', () => {
      const figure = { data: [{ x: ['a', 'b'], y: [1] }] }
      expect(figureToCsv(figure)).toBeNull()
      expect(problem(figure.data[0])).toMatch(/niet even lang/)
    })

    it('refuses an empty or all-null y', () => {
      expect(problem({ x: ['a'], y: [] })).toMatch(/ontbreken/)
      expect(problem({ x: ['a', 'b'], y: [null, null] })).toMatch(/leeg/)
    })

    it('refuses a non-numeric y', () => {
      expect(problem({ x: ['a'], y: ['veel'] })).toMatch(/numeriek/)
    })

    it('accepts a valid figure, a pie, a map and a figure with tool rows', () => {
      expect(problem({ x: ['a'], y: [1] })).toBeNull()
      expect(problem({ type: 'pie', labels: ['a'], values: [1] })).toBeNull()
      expect(problem({ type: 'choroplethmap', locations: ['PV20'], z: [12] })).toBeNull()
      const withRows = { data: [{ x: ['a', 'b'], y: [1] }], layout: { meta: { data: [{ a: 1 }] } } }
      expect(figureCsvProblem(withRows)).toBeNull()
    })
  })
})

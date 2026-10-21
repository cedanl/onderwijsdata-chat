// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { buildDashboardHtml, workbookHtml, workbookFilename } from '../dashboardHtml'
import { PLOTLY_URL } from '../plotlyBron'
import { runPage, luminance, contrast } from './helpers/pageRun'
import { layout, data } from './fixtures/plotFigure'

const FIGUUR = { data: [{ type: 'bar', x: ['2023'], y: [5], name: '</script><script>alert(1)</script>' }], layout: { title: { text: 'Instroom' } } }

const SPEC = {
  kpis: [{ label: 'Studenten', value: '38.000', trend: '+2%', trendDirection: 'up', sub: 't.o.v. 2022' }],
  figures_json: [JSON.stringify(FIGUUR)],
  narrative: '| A | B |\n|---|---|\n| 1 | 2 |\n\n<b>vet</b>',
  sources: ['DUO p01hoinges'],
}

describe('buildDashboardHtml (#254)', () => {
  const html = buildDashboardHtml(SPEC, { title: 'Instroom <HU>', instelling: 'HU', narrativeHtml: '<table><tr><td>1</td></tr></table>' })

  it('is een zelfstandige pagina met titel, KPI en bron', () => {
    expect(html.startsWith('<!DOCTYPE html>')).toBe(true)
    expect(html).toContain('<title>Instroom &lt;HU&gt;</title>')
    expect(html).toContain('38.000')
    expect(html).toContain('+2%')
    expect(html).toContain('DUO p01hoinges')
    expect(html).toContain('<table><tr><td>1</td></tr></table>')
  })

  it('geeft een grafiek de hoogte die hij meebrengt, anders 320px', () => {
    const hoog = { data: [], layout: { height: 526 } }
    const metHoogte = buildDashboardHtml({ ...SPEC, figures_json: [JSON.stringify(hoog), JSON.stringify(FIGUUR)] }, { title: 't' })
    expect(metHoogte).toContain('id="fig0" style="height:526px"')
    expect(metHoogte).toContain('id="fig1" style="height:320px"')
  })

  it('laadt Plotly één keer, van de eigen server, en tekent elke grafiek', () => {
    expect(html.match(/<script src=/g)).toHaveLength(1)
    expect(html).toContain(`<script src="${PLOTLY_URL}"></script>`)
    expect(html).not.toContain('cdn.plot.ly')
    expect(html).toContain("Plotly.newPlot('fig0'")
  })

  it('laat geen script ontsnappen uit de grafiekdata', () => {
    expect(html).not.toContain('</script><script>alert(1)')
  })
})

// The dashboard merged the layout shallowly, so the light colours of tools/plot.py stayed on
// the dark card (#574); it now shares the dark conversion of the report (#567).
describe('chart colours in a dark dashboard (#574)', () => {
  const CARD = '#1F2937'
  const xaxis2 = { showgrid: true, gridcolor: '#f0f0f0', linecolor: '#ccc', anchor: 'y' }
  const figure = { data, layout: { ...layout, xaxis2 } }
  const dashboard = (...figures) => buildDashboardHtml({ figures_json: figures.map(f => JSON.stringify(f)) }, { title: 'D' })
  const plotted = (fig, dark) => {
    const seen = runPage(dashboard(fig), { dark })
    expect(seen.errors).toEqual([])
    return { data: seen.plots[0][1], layout: seen.plots[0][2] }
  }

  it('gives title, grid, axis lines and legend dark colours', () => {
    const { layout: l } = plotted(figure, true)
    expect(l.title.font.color).not.toBe('#222')
    expect(contrast(l.title.font.color, CARD)).toBeGreaterThanOrEqual(4.5)
    for (const ax of [l.xaxis, l.yaxis, l.xaxis2]) {
      expect(ax.gridcolor).not.toBe('#f0f0f0')
      expect(ax.linecolor).not.toBe('#ccc')
      expect(luminance(ax.gridcolor)).toBeLessThan(luminance(ax.linecolor))
      expect(contrast(ax.gridcolor, CARD)).toBeGreaterThan(1.3)
    }
    expect(l.legend.bgcolor).not.toBe('rgba(255,255,255,0.8)')
    expect(l.legend.bordercolor).not.toBe('#ddd')
  })

  it('keeps the other nested layout keys and its own background, margin and font', () => {
    const { layout: l } = plotted(figure, true)
    expect(l.title).toMatchObject({ text: 'Instroom per jaar', font: { size: 16 } })
    expect(l.meta).toEqual(layout.meta)
    expect(l.xaxis).toMatchObject({ title: { text: 'Jaar' }, type: 'category', showgrid: true, zeroline: false })
    expect(l.yaxis).toMatchObject({ title: { text: 'Aantal' }, tickformat: ',d' })
    expect(l.xaxis2).toMatchObject({ anchor: 'y', showgrid: true })
    expect(l.legend).toMatchObject({ orientation: 'h', borderwidth: 1 })
    expect(l.paper_bgcolor).toBe('transparent')
    expect(l.plot_bgcolor).toBe('transparent')
    expect(l.margin).toEqual({ t: 48, r: 24, b: 48, l: 60 })
    expect(l.font).toEqual({ color: '#D1D5DB', family: 'system-ui,sans-serif', size: 12 })
  })

  it('turns a black series light in dark mode and leaves the other colours', () => {
    const { data: d } = plotted(figure, true)
    expect(d[0].marker.color).toBe('#0072B2')
    expect(contrast(d[1].marker.color, CARD)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(d[2].line.color, CARD)).toBeGreaterThanOrEqual(4.5)
    expect(d[2].line.width).toBe(2)
    expect(d[3].marker.color[0]).toBe('#B0B0B0')
    expect(d[3].marker.color.slice(1).every(c => contrast(c, CARD) >= 4.5)).toBe(true)
    expect(d[4].marker.colors.slice(0, 2)).toEqual(['#0072B2', '#F0E442'])
    expect(contrast(d[4].marker.colors[2], CARD)).toBeGreaterThanOrEqual(4.5)
    expect(d[4]).not.toHaveProperty('line')
    expect(d[4].marker).not.toHaveProperty('color')
  })

  it('passes the figure unchanged in light mode', () => {
    const { data: d, layout: l } = plotted(figure, false)
    expect(d).toEqual(figure.data)
    expect(l).toEqual({
      ...figure.layout,
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      margin: { t: 48, r: 24, b: 48, l: 60 },
      font: { color: '#374151', family: 'system-ui,sans-serif', size: 12 },
    })
  })

  it('gives every chart of a dark dashboard the same dark colours, without touching the figure', () => {
    const before = JSON.parse(JSON.stringify(figure))
    const seen = runPage(buildDashboardHtml({ figures_json: [figure, JSON.stringify(figure)] }, { title: 'D' }), { dark: true })
    expect(seen.errors).toEqual([])
    expect(seen.plots).toHaveLength(2)
    expect(seen.plots[0][2].title.font.color).not.toBe('#222')
    expect(seen.plots[1][1]).toEqual(seen.plots[0][1])
    expect(seen.plots[1][2]).toEqual(seen.plots[0][2])
    expect(figure).toEqual(before)
  })

  it('handles a string title, no title, no axes, no layout and no data in dark mode', () => {
    expect(plotted({ data: [], layout: { title: 'x' } }, true).layout.title).toBe('x')
    const bare = plotted({ data: [{ type: 'pie', values: [1] }], layout: {} }, true)
    expect(bare.layout).not.toHaveProperty('title')
    expect(bare.layout).not.toHaveProperty('xaxis')
    expect(bare.layout).not.toHaveProperty('legend')
    expect(bare.data).toEqual([{ type: 'pie', values: [1] }])
    expect(plotted({ data: [{ type: 'bar', y: [1] }] }, true).data).toEqual([{ type: 'bar', y: [1] }])
    expect(plotted({ layout: {} }, true).data).toEqual([])
  })

  // #474 in the dark branch: the title only reaches Plotly as text.
  it('renders a title with </script> as chart text in dark mode', () => {
    const TITLE = '</script><img src=x onerror=alert(1)>'
    const html = dashboard({ data: [], layout: { title: TITLE } })
    expect(html.match(/<script/g).length).toBe(html.match(/<\/script>/g).length)
    const seen = runPage(html, { dark: true })
    expect(seen.images).toBe(0)
    expect(seen.dialogs).toEqual([])
    expect(seen.errors).toEqual([])
    expect(seen.plots[0][2].title).toBe(TITLE)
  })
})

// #651: the rounding note is a text line under the chart, also in the download; a stored dashboard still has it as a
// subtitle in the figure.
describe('rounding note under a dashboard chart (#651)', () => {
  const NOOT = 'De aantallen zijn door CBS afgerond op 10-tallen: een som, verschil of percentage daarvan is niet exact.'
  const nieuw = { data: [], layout: { title: { text: 'Instroom' }, meta: { afrondingsnoot: NOOT } } }
  const oud = { data: [], layout: { title: { text: 'Uitval', subtitle: { text: 'De aantallen zijn door CBS afgerond op 10-tallen: een<br>som, verschil of percentage daarvan is niet exact.' } } } }
  const kaart = (html, i) => html.slice(html.indexOf(`<div class="card"><div id="fig${i}"`), html.indexOf(`Plotly.newPlot('fig${i}'`))

  it('puts the note as a line in the chart card, after the chart, for a new and a stored figure', () => {
    const html = buildDashboardHtml({ figures_json: [JSON.stringify(nieuw), oud, JSON.stringify(FIGUUR)] }, { title: 'D' })
    for (const i of [0, 1]) {
      expect(kaart(html, i)).toMatch(new RegExp(`<div id="fig${i}" style="height:320px"></div><p class="figuur-noot">${NOOT}</p></div>\\s*<script>`))
    }
    expect(kaart(html, 2)).not.toContain('figuur-noot')
    const seen = runPage(html)
    expect(seen.errors).toEqual([])
    expect(seen.plots.map(p => p[2].title)).toEqual([{ text: 'Instroom' }, { text: 'Uitval' }, { text: 'Instroom' }])
    expect(html).not.toContain('subtitle')
  })

  it('escapes the note', () => {
    const html = buildDashboardHtml({ figures_json: [{ data: [], layout: { meta: { afrondingsnoot: '<img src=x onerror=alert(1)> & "c"' } } }] }, { title: 'D' })
    expect(html).toContain('<p class="figuur-noot">&lt;img src=x onerror=alert(1)&gt; &amp; &quot;c&quot;</p>')
    expect(runPage(html, { dark: true }).images).toBe(0)
  })

  it('gives the note at least .8rem and a light colour in the dark media query', () => {
    const html = buildDashboardHtml({ figures_json: [nieuw] }, { title: 'D' })
    expect(html).toMatch(/\.figuur-noot\{[^}]*font-size:\.8rem/)
    const donker = html.slice(html.indexOf('@media(prefers-color-scheme:dark)'))
    const kleur = donker.match(/([^{}]*\.figuur-noot[^{}]*)\{color:(#[0-9A-F]{6})\}/i)
    expect(kleur).not.toBeNull()
    expect(contrast(kleur[2], '#1F2937')).toBeGreaterThanOrEqual(4.5)
  })
})

describe('workbookHtml', () => {
  it('geeft een rapport zijn eigen HTML', async () => {
    expect(await workbookHtml({ title: 'R', htmlContent: '<html>rapport</html>' })).toBe('<html>rapport</html>')
  })

  it('bouwt een dashboard uit zijn spec, met de toelichting als veilige markdown', async () => {
    const html = await workbookHtml({ title: 'D', dashboardSpec: SPEC })
    expect(html).toContain('<table>')
    expect(html).not.toContain('<b>vet</b>')
  })

  it('heeft niets voor een ingebouwd dashboard', async () => {
    expect(await workbookHtml({ title: 'Mijn instelling', builtin: true })).toBeNull()
  })

  it('maakt een bestandsnaam van de titel', () => {
    expect(workbookFilename({ title: 'Instroom HU 2023/24' })).toBe('Instroom_HU_2023_24.html')
  })
})

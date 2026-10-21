import { describe, it, expect } from 'vitest'
import { buildReportHtml } from '../reportHtml.js'
import { buildDashboardHtml } from '../dashboardHtml.js'
import { PLOTLY_URL } from '../plotlyBron'
import { metThema } from '../reportThema'
import { runPage, runPageNaTekenen, luminance, contrast } from './helpers/pageRun'
import { layout, data } from './fixtures/plotFigure'

const fullSpec = {
  title: 'Instroom ROC van Flevoland 2018–2024',
  onderzoeksvraag: 'Hoe ontwikkelt de eerstejaars instroom van ROC van Flevoland zich over de jaren?',
  definities: [
    { begrip: 'Eerstejaars', definitie: 'Student die voor het eerst staat ingeschreven bij een opleiding' },
    { begrip: 'Instroom', definitie: 'Aantal nieuw ingeschreven studenten in een kalenderjaar' },
  ],
  beantwoordt: ['De jaarlijkse ontwikkeling van de instroom', 'Het aantal mbo-studenten per sector'],
  beantwoordt_niet: ['De internationale studentenmigratie', 'De arbeidsmarktuitstroom van gediplomeerden'],
  visualisaties: [
    {
      titel: 'Instroom per jaar',
      toelichting: 'De instroom stijgt gestaag, met een uitschieter in 2022.',
      figure_json: '{"data":[],"layout":{"title":"x"}}',
    },
  ],
  conclusie: 'De instroom is tussen 2018 en 2024 met **18%** gestegen.',
  bronnen: ['DUO — Instroom in het mbo (p01hoinges)', 'CBS — Regionale arbeidsmarktcijfers'],
  auteur: 'jansen',
  datum: '1 september 2026',
}

// The one phone rule of the report stylesheet.
const phoneCss = html => {
  const phone = html.slice(html.indexOf('@media(max-width:640px)'))
  return phone.slice(0, phone.indexOf('}}') + 2)
}

describe('buildReportHtml', () => {
  // CH-34 kept the server's 100 px for a title note; the note is now a line under the chart (#651), so every chart
  // gets the export's own 48 px, a stored one with its note as subtitle too.
  it('gives every chart the top margin of the export, also a stored one with a note under its title', () => {
    const layout = { title: { text: 'HO', subtitle: { text: 'Afgerond op 10-tallen' } }, margin: { t: 100 } }
    const spec = { ...fullSpec, visualisaties: [{ titel: 'Studenten in het ho', figure_json: JSON.stringify({ data: [], layout }) }] }
    expect(buildReportHtml(spec)).toContain('margin:{t:48,')
    expect(buildReportHtml(spec)).not.toContain('margin:{t:100,')
    expect(buildReportHtml(fullSpec)).toContain('margin:{t:48,')
  })

  // Horizontal bars bring their own height; the fixed 360 px squashed 18 universities. The others get the
  // base height from the CSS, 420 px on a phone (#571).
  it('gives a chart the height it brings, and the base height from the CSS otherwise', () => {
    const spec = { ...fullSpec, visualisaties: [{ titel: 'WO', figure_json: JSON.stringify({ data: [], layout: { height: 526 } }) }] }
    expect(buildReportHtml(spec)).toContain('<div id="rp0" class="plot" style="height:526px">')
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('<div id="rp0" class="plot plot-auto">')
    expect(html).toContain('.plot-auto{height:360px}')
    expect(phoneCss(html)).toContain('.plot-auto{height:420px}')
  })

  // On a phone two nested card paddings left the chart 260 px; long names fell off the left. The chart now
  // also bleeds into the padding of the outer card (#571).
  it('gives a chart the full card width on a phone', () => {
    expect(phoneCss(buildReportHtml(fullSpec))).toContain('.vis .card{padding:0;margin:0 -16px}')
  })

  it('returns valid HTML with doctype and title', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<title>Instroom ROC van Flevoland 2018–2024</title>')
  })

  it('shows the research question prominently at the top', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Onderzoeksvraag')
    expect(html).toContain('Hoe ontwikkelt de eerstejaars instroom')
  })

  it('lists the chosen definitions', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Gekozen definities')
    expect(html).toContain('Eerstejaars')
    expect(html).toContain('Student die voor het eerst staat ingeschreven')
  })

  it('shows what the report does and does not answer', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Wat dit rapport wel beantwoordt')
    expect(html).toContain('De jaarlijkse ontwikkeling van de instroom')
    expect(html).toContain('Wat dit rapport niet beantwoordt')
    expect(html).toContain('De internationale studentenmigratie')
  })

  it('embeds visualisations with title, explanation and plotly figure', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Instroom per jaar')
    expect(html).toContain('De instroom stijgt gestaag')
    expect(html).toContain('plotly')
    expect(html).toContain('rp0')
  })

  // #486: geen verzoek naar een derde partij bij het openen van een rapport.
  it('laadt Plotly één keer in de head, van de eigen server, en alleen met een grafiek', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).not.toContain('cdn.plot.ly')
    expect(html.match(/<script src=/g)).toHaveLength(1)
    expect(html.indexOf(`<script src="${PLOTLY_URL}"></script>`)).toBeLessThan(html.indexOf('<style>'))
    expect(buildReportHtml({ ...fullSpec, visualisaties: [] })).not.toContain('<script src=')
  })

  it('renders a Conclusie heading with markdown', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Conclusie')
    expect(html).toContain('18%')
    expect(html).toContain('<strong>18%</strong>')
  })

  it('lists the sources', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Bronnen')
    expect(html).toContain('DUO — Instroom in het mbo (p01hoinges)')
  })

  it('shows generation date and author', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('1 september 2026')
    expect(html).toContain('jansen')
  })

  it('includes the instelling badge when provided', () => {
    const html = buildReportHtml(fullSpec, { instelling: 'Hogeschool Utrecht' })
    expect(html).toContain('Hogeschool Utrecht')
  })

  it('handles an empty spec gracefully', () => {
    const html = buildReportHtml({})
    expect(html).toContain('<!DOCTYPE html>')
  })

  it('escapes HTML to prevent XSS', () => {
    const evil = {
      title: '<img onerror=alert(1)>',
      onderzoeksvraag: '<script>alert("x")</script>',
      conclusie: 'nog <b>vet</b>',
      beantwoordt: ['<i>cursief</i>'],
      bronnen: ['<svg onload=alert(2)>'],
    }
    const html = buildReportHtml(evil, { instelling: '<b>evil</b>' })
    expect(html).not.toContain('<img onerror=alert(1)>')
    expect(html).not.toContain('<script>alert')
    expect(html).not.toContain('<svg onload=alert(2)>')
    expect(html).not.toContain('<b>evil</b>')
    expect(html).toContain('&lt;img onerror=alert(1)&gt;')
    expect(html).toContain('&lt;script&gt;')
    expect(html).toContain('&lt;svg onload=alert(2)&gt;')
    expect(html).toContain('&lt;b&gt;evil&lt;/b&gt;')
  })

  it('gives each section a heading under the single h1 (#424)', () => {
    const html = buildReportHtml({ ...fullSpec, conclusie: '# Kort\nDe instroom steeg.' })
    const kop = n => [...html.matchAll(new RegExp(`<h${n}[ >][^]*?</h${n}>`, 'g'))].map(m => m[0].replace(/<[^>]+>/g, ''))
    expect(kop(1)).toEqual(['Instroom ROC van Flevoland 2018–2024'])
    expect(kop(2)).toEqual(expect.arrayContaining(['Reikwijdte', 'Gekozen definities', 'Visualisaties', 'Conclusie', 'Bronnen']))
    expect(kop(3)).toEqual(expect.arrayContaining(['Instroom per jaar', 'Kort']))
  })
})

describe('figure JSON in an inline script (#474)', () => {
  const TITLE = '</script><img src=x onerror=alert(1)>'
  const figureJson = JSON.stringify({ data: [], layout: { title: TITLE } })
  const html = buildReportHtml({ ...fullSpec, visualisaties: [{ titel: 'Evil', figure_json: figureJson }] })

  it('leaves only the structural script tags in the report', () => {
    expect(html).not.toContain('</script><img')
    expect(html.match(/<script/g).length).toBe(html.match(/<\/script>/g).length)
  })

  it('renders a report title with </script> as chart text, not as markup', () => {
    const seen = runPage(html)
    expect(seen.images).toBe(0)
    expect(seen.dialogs).toEqual([])
    expect(seen.errors).toEqual([])
    expect(seen.plots).toHaveLength(1)
    expect(seen.plots[0][1]).toEqual([])
    expect(seen.plots[0][2].title).toBe(TITLE)
  })

  it('renders a dashboard title with </script> as chart text, not as markup', () => {
    const seen = runPage(buildDashboardHtml({ figures_json: [figureJson] }, { title: 'D' }))
    expect(seen.images).toBe(0)
    expect(seen.dialogs).toEqual([])
    expect(seen.errors).toEqual([])
    expect(seen.plots[0][2].title).toBe(TITLE)
  })
})

// The light colours tools/plot.py bakes into a figure stayed in the dark report (#567).
describe('chart colours in a dark report (#567)', () => {
  const CARD = '#1F2937'
  const PLOT_BG = '#111827'
  const figure = { data, layout }
  const report = (...figures) => buildReportHtml({
    ...fullSpec,
    visualisaties: figures.map((f, i) => ({ titel: `G${i}`, figure_json: JSON.stringify(f) })),
  })
  const plotted = (fig, dark) => {
    const seen = runPage(report(fig), { dark })
    expect(seen.errors).toEqual([])
    return { data: seen.plots[0][1], layout: seen.plots[0][2] }
  }

  it('gives title, grid, axis lines and legend dark colours', () => {
    const { layout: l } = plotted(figure, true)
    expect(l.title.font.color).not.toBe('#222')
    expect(contrast(l.title.font.color, CARD)).toBeGreaterThanOrEqual(4.5)
    for (const ax of [l.xaxis, l.yaxis]) {
      expect(ax.gridcolor).not.toBe('#f0f0f0')
      expect(ax.linecolor).not.toBe('#ccc')
      expect(luminance(ax.gridcolor)).toBeLessThan(luminance(ax.linecolor))
      expect(contrast(ax.gridcolor, PLOT_BG)).toBeGreaterThan(1.3)
      expect(contrast(ax.gridcolor, PLOT_BG)).toBeLessThan(3)
    }
    expect(l.legend.bgcolor).not.toBe('rgba(255,255,255,0.8)')
    expect(l.legend.bgcolor).toMatch(/^rgba\(\d+,\d+,\d+,0?\.\d+\)$/)
    expect(l.legend.bordercolor).not.toBe('#ddd')
  })

  it('keeps the other nested layout keys in dark mode', () => {
    const { layout: l } = plotted(figure, true)
    expect(l.title).toMatchObject({ text: 'Instroom per jaar', font: { size: 16 } })
    expect(l.meta).toEqual(layout.meta)
    expect(l.xaxis).toMatchObject({ title: { text: 'Jaar' }, type: 'category', showgrid: true, zeroline: false })
    expect(l.yaxis).toMatchObject({ title: { text: 'Aantal' }, tickformat: ',d' })
    expect(l.legend).toMatchObject({ orientation: 'h', borderwidth: 1 })
    expect(l.plot_bgcolor).toBe(PLOT_BG)
    expect(l.margin.t).toBe(48)
  })

  it('turns a black series light in dark mode and leaves the other colours', () => {
    const { data: d } = plotted(figure, true)
    expect(d[0].marker.color).toBe('#0072B2')
    expect(contrast(d[1].marker.color, PLOT_BG)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(d[2].line.color, PLOT_BG)).toBeGreaterThanOrEqual(4.5)
    expect(d[2].line.width).toBe(2)
    expect(d[3].marker.color[0]).toBe('#B0B0B0')
    expect(d[3].marker.color.slice(1).every(c => contrast(c, PLOT_BG) >= 4.5)).toBe(true)
    expect(d[4].marker.colors.slice(0, 2)).toEqual(['#0072B2', '#F0E442'])
    expect(contrast(d[4].marker.colors[2], CARD)).toBeGreaterThanOrEqual(4.5)
    expect(d[4]).not.toHaveProperty('line')
    expect(d[4].marker).not.toHaveProperty('color')
  })

  it('passes the figure unchanged in light mode', () => {
    const { data: d, layout: l } = plotted(figure, false)
    expect(d).toEqual(data)
    expect(l).toEqual({
      ...layout,
      paper_bgcolor: 'transparent',
      plot_bgcolor: '#F9FAFB',
      margin: { t: 48, r: 24, b: 48, l: 60 },
      font: { color: '#374151', family: 'system-ui,sans-serif', size: 12 },
    })
  })

  it('gives every chart of a dark report the same dark colours', () => {
    const seen = runPage(report(figure, figure), { dark: true })
    expect(seen.errors).toEqual([])
    expect(seen.plots).toHaveLength(2)
    expect(seen.plots[1][1]).toEqual(seen.plots[0][1])
    expect(seen.plots[1][2]).toEqual(seen.plots[0][2])
  })

  it('handles a string title, no title and no axes in dark mode', () => {
    expect(plotted({ data: [], layout: { title: 'x' } }, true).layout.title).toBe('x')
    const bare = plotted({ data: [{ type: 'pie', values: [1] }], layout: {} }, true)
    expect(bare.layout).not.toHaveProperty('title')
    expect(bare.layout).not.toHaveProperty('xaxis')
    expect(bare.layout).not.toHaveProperty('legend')
    expect(bare.data).toEqual([{ type: 'pie', values: [1] }])
    expect(plotted({ layout: {} }, true).data).toBeUndefined()
  })
})

// Under each chart its own source line from code, with a link to the open-data source (#569).
describe('bronregel onder een grafiek (#569)', () => {
  const cbs = {
    bron: 'CBS', dataset: '85423NED',
    tekst: 'CBS · Hoger onderwijs; ingeschrevenen (85423NED), 2019/20 t/m 2024/25, status Voorlopig',
    url: 'https://opendata.cbs.nl/ODataApi/OData/85423NED',
  }
  const duo = {
    bron: 'DUO', dataset: 'p01hoinges',
    tekst: 'DUO · Ingeschrevenen hoger onderwijs (p01hoinges), bestand Ingeschrevenen hbo, 2023/24',
    url: 'https://onderwijsdata.duo.nl/dataset/p01hoinges',
  }
  const report = (...bronnen) => buildReportHtml({
    ...fullSpec,
    visualisaties: bronnen.map((bron, i) => ({ titel: `G${i}`, figure_json: '{"data":[],"layout":{}}', toelichting: `T${i}`, bron })),
  })
  const regels = html => [...html.matchAll(/<p class="vis-bron">([^]*?)<\/p>/g)].map(m => m[1])

  it('toont onder elke grafiek de regel van haar eigen dataset, met de link', () => {
    const html = report(cbs, duo)
    const [eerste, tweede] = regels(html)
    expect(regels(html)).toHaveLength(2)
    expect(eerste).toContain('Bron: CBS · Hoger onderwijs; ingeschrevenen (85423NED), 2019/20 t/m 2024/25, status Voorlopig')
    expect(eerste).toContain('<a href="https://opendata.cbs.nl/ODataApi/OData/85423NED" target="_blank" rel="noopener noreferrer">Bekijk de bron bij CBS</a>')
    expect(tweede).toContain('Bron: DUO · Ingeschrevenen hoger onderwijs (p01hoinges), bestand Ingeschrevenen hbo, 2023/24')
    expect(tweede).toContain('href="https://onderwijsdata.duo.nl/dataset/p01hoinges"')
    expect(tweede).toContain('Bekijk de bron bij DUO')
  })

  it('staat direct onder de grafiek, vóór de toelichting', () => {
    const html = report(cbs)
    expect(html.indexOf('id="rp0"')).toBeLessThan(html.indexOf('class="vis-bron"'))
    expect(html.indexOf('class="vis-bron"')).toBeLessThan(html.indexOf('class="vis-note"'))
  })

  it.each([[null], [undefined], [{}], [{ tekst: '' }]])('zegt "Bron niet vastgesteld" voor bron %j', bron => {
    const [regel] = regels(report(bron))
    expect(regel).toBe('Bron niet vastgesteld')
  })

  it('toont de regel zonder link als de catalogus geen link kent', () => {
    const [regel] = regels(report({ ...cbs, url: null }))
    expect(regel).toBe(`Bron: ${cbs.tekst}`)
    expect(regel).not.toContain('<a ')
  })

  it('maakt alleen van een http(s)-adres een link en escapet aanhalingstekens erin', () => {
    const [vreemd] = regels(report({ ...cbs, url: 'javascript:alert(1)' }))
    expect(vreemd).not.toContain('<a ')
    expect(vreemd).not.toContain('javascript:')
    const [quotes] = regels(report({ ...cbs, url: 'https://example.org/data?q="x"&y=\'z\'' }))
    expect(quotes).toContain('href="https://example.org/data?q=&quot;x&quot;&amp;y=&#39;z&#39;"')
    expect(quotes).not.toContain('"x"')
  })

  it('escapet de tekst van de regel', () => {
    const [regel] = regels(report({ ...cbs, tekst: '<img src=x onerror=alert(1)>', bron: '<b>CBS</b>' }))
    expect(regel).not.toContain('<img')
    expect(regel).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(regel).toContain('bij &lt;b&gt;CBS&lt;/b&gt;')
  })

  it('leest in beide thema\'s met genoeg contrast op de kaart', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toMatch(/\.vis-bron\{[^}]*color:#6B7280/)
    expect(contrast('#6B7280', '#FFFFFF')).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#2563EB', '#FFFFFF')).toBeGreaterThanOrEqual(4.5)
    const donker = html.slice(html.indexOf('@media(prefers-color-scheme:dark)'))
    expect(donker).toContain('.vis-bron{color:#9CA3AF}')
    expect(donker).toContain('.vis-bron a{color:#60A5FA}')
    expect(contrast('#9CA3AF', '#1F2937')).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#60A5FA', '#1F2937')).toBeGreaterThanOrEqual(4.5)
  })
})

// The app's theme choice wins over the OS preference (#568): a class on <html> picks the theme, no class
// leaves it to prefers-color-scheme, as before.
describe('rapportthema volgt de app-keuze (#568)', () => {
  const html = buildReportHtml(fullSpec)
  const css = html.slice(html.indexOf('<style>'), html.indexOf('</style>'))
  const donker = css.slice(css.indexOf('@media(prefers-color-scheme:dark)'))

  it('heeft donkere regels voor html.dark, en als terugval voor de OS-voorkeur alleen zonder html.light', () => {
    expect(css).toContain('html.dark body{color:#F9FAFB;background:#111827}')
    expect(css).toContain('html.dark .card{background:#1F2937}')
    expect(donker).toContain('html:not(.light) body{color:#F9FAFB;background:#111827}')
    expect(donker).toContain('html:not(.light) .card{background:#1F2937}')
    // Every dark rule exists in both forms, and a selector list gets the prefix on each part.
    const regels = blok => [...blok.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(m => [m[1].trim(), m[2]])
    const expliciet = regels(css.slice(css.indexOf('html.dark'), css.indexOf('@media(prefers-color-scheme:dark)')))
    const terugval = regels(donker.slice(donker.indexOf('{') + 1))
    expect(expliciet.length).toBeGreaterThan(10)
    expect(terugval.map(([sel, decl]) => [sel.replaceAll('html:not(.light) ', 'html.dark '), decl])).toEqual(expliciet)
    expect(expliciet.every(([sel]) => sel.split(',').every(s => s.startsWith('html.dark ')))).toBe(true)
    expect(donker).not.toMatch(/\{\s*body\{/)
  })

  it('geeft de grafiek donkere kleuren bij html.dark, ook als het OS licht is', () => {
    const seen = runPage(metThema(html, 'dark'), { dark: false })
    expect(seen.errors).toEqual([])
    expect(seen.plots[0][2].plot_bgcolor).toBe('#111827')
    expect(seen.plots[0][2].font.color).toBe('#D1D5DB')
  })

  it('houdt de grafiek licht bij html.light, ook als het OS donker is', () => {
    const seen = runPage(metThema(html, 'light'), { dark: true })
    expect(seen.errors).toEqual([])
    expect(seen.plots[0][2].plot_bgcolor).toBe('#F9FAFB')
    expect(seen.plots[0][2].font.color).toBe('#374151')
  })

  it('volgt zonder klasse de OS-voorkeur, zoals voorheen', () => {
    expect(runPage(html, { dark: true }).plots[0][2].plot_bgcolor).toBe('#111827')
    expect(runPage(html, { dark: false }).plots[0][2].plot_bgcolor).toBe('#F9FAFB')
  })
})

// Measured on 390 px (#571): the chart title fell off the right, the legend title beside the items made the
// legend wider than the chart, and the names on the y-axis of horizontal bars left 64 px of plot area.
describe('grafiek op een telefoon (#571)', () => {
  const axis = { showgrid: true, gridcolor: '#f0f0f0', linecolor: '#ccc', zeroline: false }
  const lijn = {
    data: [
      { type: 'scatter', mode: 'lines', name: 'Economie en bedrijfskunde', x: ['2015', '2016'], y: [1, 2] },
      { type: 'scatter', mode: 'lines', name: 'Landbouw en natuurlijke omgeving', x: ['2015', '2016'], y: [2, 3] },
    ],
    layout: {
      title: { text: 'Ingeschrevenen per sector 2015/16–2024/25 naar onderdeel', font: { size: 16, color: '#222' } },
      xaxis: { ...axis, title: { text: 'Studiejaar' }, type: 'category', tickfont: { color: '#333' } },
      yaxis: { ...axis, title: { text: 'Aantal' }, tickformat: ',' },
      legend: { bgcolor: 'rgba(255,255,255,0.8)', bordercolor: '#ddd', borderwidth: 1, orientation: 'h', title: { text: 'Onderdeel' } },
      margin: { t: 60, b: 50, l: 70, r: 20 },
    },
  }
  const namen = ['Hogeschool van Amsterdam', 'HAN University of Applied Sciences', 'Avans']
  const staven = {
    data: [{ type: 'bar', orientation: 'h', x: [3, 2, 1], y: namen, text: ['3', '2', '1'] }],
    layout: { title: { text: 'Kort' }, yaxis: { ...axis, autorange: 'reversed', automargin: true }, xaxis: axis, height: 300, showlegend: false },
  }
  const report = fig => buildReportHtml({ ...fullSpec, visualisaties: [{ titel: 'G', figure_json: JSON.stringify(fig) }] })
  const plotted = (fig, width) => {
    const seen = runPage(report(fig), { width })
    expect(seen.errors).toEqual([])
    return { id: seen.plots[0][0], data: seen.plots[0][1], layout: seen.plots[0][2], dom: seen }
  }

  it('breekt een lange titel af, maakt hem kleiner en geeft de marge erboven ruimte per extra regel', () => {
    const { layout: l } = plotted(lijn, 390)
    expect(l.title.text).toBe('Ingeschrevenen per sector 2015/16–2024/25<br>naar onderdeel')
    expect(l.title.font).toEqual({ size: 14, color: '#222' })
    expect(l.title).not.toHaveProperty('pad')
    expect(l.margin.t).toBe(48 + 17)
  })

  // The title of a stored chart with a note hangs from the top edge (CH-34); wrapped, its first line stuck out above
  // the chart. The note itself is a line under the chart now (#651).
  it('houdt een afgebroken titel met noot binnen de figuur', () => {
    const metNoot = { ...lijn, layout: { ...lijn.layout, title: { ...lijn.layout.title, yref: 'container', yanchor: 'top', y: 0.98, subtitle: { text: 'Afgerond op 10-tallen', font: { size: 11, color: '#666' } } }, margin: { t: 100 } } }
    const { layout: l } = plotted(metNoot, 390)
    expect(l.title).toMatchObject({ yref: 'container', yanchor: 'top', y: 0.98, pad: { t: 10 } })
    expect(l.title).not.toHaveProperty('subtitle')
    expect(l.margin.t).toBe(48 + 17)
    const kort = { ...metNoot, layout: { ...metNoot.layout, title: { ...metNoot.layout.title, text: 'Kort' } } }
    expect(plotted(kort, 390).layout.title).not.toHaveProperty('pad')
  })

  it('zet de legendatitel boven de items en maakt legenda- en tickletters kleiner', () => {
    const { layout: l } = plotted(lijn, 390)
    expect(l.legend.title).toEqual({ text: 'Onderdeel', side: 'top' })
    expect(l.legend.font).toEqual({ size: 11 })
    expect(l.legend).toMatchObject({ orientation: 'h', borderwidth: 1 })
    expect(l.xaxis.tickfont).toEqual({ color: '#333', size: 11 })
    expect(l.yaxis.tickfont).toEqual({ size: 11 })
    expect(l.xaxis).toMatchObject({ title: { text: 'Studiejaar' }, type: 'category', showgrid: true })
  })

  it('breekt lange namen op de y-as van liggende staven af', () => {
    const { layout: l, data: d, id } = plotted(staven, 390)
    expect(l.yaxis.tickvals).toEqual(namen)
    expect(l.yaxis.ticktext).toEqual(['Hogeschool van Amsterdam', 'HAN University of<br>Applied Sciences', 'Avans'])
    expect(l.yaxis).toMatchObject({ autorange: 'reversed', automargin: true })
    expect(d).toEqual([{ ...staven.data[0], textfont: { size: 11 } }])
    expect(id).toBe('rp0')
  })

  it('laat een korte titel, een legenda zonder titel en staande staven met rust', () => {
    const kort = { data: [{ type: 'bar', x: ['HU', 'UU'], y: [1, 2] }], layout: { title: { text: 'Kort' }, legend: { orientation: 'h' }, xaxis: axis } }
    const { layout: l } = plotted(kort, 390)
    expect(l.title).toEqual({ text: 'Kort', font: { size: 14 } })
    expect(l.margin.t).toBe(48)
    expect(l.legend).toEqual({ orientation: 'h', font: { size: 11 } })
    expect(l.xaxis).not.toHaveProperty('tickvals')
  })

  it('verandert niets op een breed scherm', () => {
    const { layout: l, data: d } = plotted(lijn, 1024)
    expect(l.title).toEqual(lijn.layout.title)
    expect(l.legend).toEqual(lijn.layout.legend)
    expect(l.xaxis).toEqual(lijn.layout.xaxis)
    expect(d).toEqual(lijn.data)
    expect(plotted(staven, 1024).layout.yaxis).toEqual(staven.layout.yaxis)
  })

  it('zet op een telefoon de badge onder de titel, breekt lange woorden en vergroot de kleinste letters', () => {
    const html = buildReportHtml(fullSpec)
    expect(phoneCss(html)).toContain('.header-top{flex-direction:column}')
    expect(phoneCss(html)).toContain('.header-label,.section-label,.manifest,.footer{font-size:.75rem}')
    expect(html).toContain('.header h1,.vraag-text,.scope-col li,.def-desc,.vis-note,.vis-noot,.vis-bron,.prose,.bronnen li,.manifest{overflow-wrap:anywhere}')
  })
})

describe('manifest (#345)', () => {
  const manifest = {
    model: 'anthropic/claude-sonnet-4-6',
    model_naam: 'Claude Sonnet',
    model_versie: 'claude-sonnet-4-6-20250929',
    sampling: { seed: 42, seed_toegepast: false, temperature: 0, temperature_toegepast: true },
    prompt_hash: 'abc123def456',
    catalogus: 'bd4942907ddd',
    app: '2.2.0',
    data_as_of: [
      { bron: 'cbs', dataset: '85423NED', laatste_update: '2026-09-15', periodestatus: ['Voorlopig'] },
      { bron: 'duo', dataset: 'p01hoinges', herladen_op: '11-10-2026' },
      { bron: 'uwv', dataset: 'uwv-open-match-data', peilmoment: 'peildatum 2023-05-16' },
    ],
    gemaakt_op: '12-10-2026',
  }

  it('toont de verantwoording compact in rapport en export', () => {
    const html = buildReportHtml({ ...fullSpec, manifest })
    expect(html).toContain('Verantwoording:')
    expect(html).toContain('model Claude Sonnet (claude-sonnet-4-6-20250929)')
    expect(html).not.toContain('anthropic/')
    expect(html).toContain('seed niet toegepast')
    expect(html).toContain('prompt abc123def456')
    expect(html).toContain('catalogus bd4942907ddd')
    expect(html).toContain('CBS 85423NED (bijgewerkt 2026-09-15, status Voorlopig)')
    expect(html).toContain('DUO p01hoinges (herladen 11-10-2026)')
    expect(html).toContain('UWV uwv-open-match-data (peildatum 2023-05-16)')
  })

  it('een ouder manifest zonder model_naam toont het id zonder provider (BEV-10)', () => {
    const { model_naam: _weg, ...ouder } = manifest
    const html = buildReportHtml({ ...fullSpec, manifest: { ...ouder, model: 'azure_ai/claude-sonnet-5-5' } })
    expect(html).toContain('model claude-sonnet-5-5 (claude-sonnet-4-6-20250929)')
    expect(html).not.toContain('azure_ai/')
  })

  it('zonder manifest geen verantwoordingsblok', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).not.toContain('Verantwoording:')
  })
})

describe('rapportgrafiek op een telefoon, restpunten (#579)', () => {
  const noot = 'De aantallen zijn door CBS afgerond op 10-tallen: een<br>som, verschil of percentage daarvan is niet exact.'
  const metTitel = (text, extra = {}) => ({
    data: [{ type: 'scatter', mode: 'lines+markers+text', x: [2019, 2020], y: [2350, 2060], text: ['2.350', '2.060'] }],
    layout: { title: { text, font: { size: 16, color: '#222' }, yref: 'container', yanchor: 'top', y: 0.98, ...extra }, margin: { t: 100, b: 50, l: 70, r: 20 } },
  })
  const rapport = (titel, fig) => buildReportHtml({ ...fullSpec, visualisaties: [{ titel, figure_json: JSON.stringify(fig) }] })
  const getekend = (html, width) => {
    const seen = runPage(html, { width })
    expect(seen.errors).toEqual([])
    return { data: seen.plots[0][1], layout: seen.plots[0][2] }
  }
  const vis = html => html.slice(html.indexOf('<div class="vis">'), html.indexOf('<div class="card"><div id="rp0"'))
  const onderGrafiek = html => html.slice(html.indexOf('</script>', html.indexOf('<div id="rp0"')), html.indexOf('<p class="vis-bron">'))

  describe('punt 1: de titel één keer', () => {
    it('laat een figuurtitel die gelijk is aan de kop weg en zet de noot als tekst onder de grafiek', () => {
      const html = rapport("Studenten mbo 3 handel 2019/'20-2025/'26", metTitel("Studenten mbo 3 handel 2019/'20–2025/'26", { subtitle: { text: noot } }))
      expect(vis(html)).toMatch(/<h3 class="vis-title">[^<]*<\/h3>\s*$/)
      expect(onderGrafiek(html)).toMatch(/^<\/script>\s*<p class="vis-noot">De aantallen zijn door CBS afgerond op 10-tallen: een som, verschil of percentage daarvan is niet exact\.<\/p>\s*$/)
      for (const width of [390, 1024]) {
        const { layout: l } = getekend(html, width)
        expect(l).not.toHaveProperty('title')
        expect(l.margin.t).toBe(16)
      }
    })

    it('negeert hoofdletters, witruimte, streepjes en een punt aan het eind', () => {
      const html = rapport('Instroom  per jaar.', metTitel('instroom per jaar'))
      expect(getekend(html, 390).layout).not.toHaveProperty('title')
      expect(html).not.toContain('class="vis-noot"')
    })

    it('laat een figuurtitel die meer zegt dan de kop staan, met de noot als tekst onder de grafiek', () => {
      const html = rapport('Ingeschrevenen per hogeschool 2024/25', metTitel('Ingeschrevenen per hogeschool 2024/25 (afgerond op tientallen)', { subtitle: { text: noot } }))
      const { layout: l } = getekend(html, 1024)
      expect(l.title.text).toBe('Ingeschrevenen per hogeschool 2024/25 (afgerond op tientallen)')
      expect(l.title).not.toHaveProperty('subtitle')
      expect(l.margin.t).toBe(48)
      expect(onderGrafiek(html)).toContain('<p class="vis-noot">De aantallen zijn door CBS afgerond op 10-tallen: een som,')
    })

    it('houdt de figuurtitel als het model geen kop gaf (de kop is dan "Visualisatie 1")', () => {
      const html = rapport('', metTitel('Instroom per jaar'))
      expect(html).toContain('<h3 class="vis-title">Visualisatie 1</h3>')
      expect(getekend(html, 1024).layout.title.text).toBe('Instroom per jaar')
    })

    it('zet de noot als platte tekst neer', () => {
      const html = rapport('HO', metTitel('HO', { subtitle: { text: 'a<img src=x onerror=alert(1)>b "c"' } }))
      expect(onderGrafiek(html)).toContain('<p class="vis-noot">ab &quot;c&quot;</p>')
      expect(html).not.toContain('<img src=x')
    })

    it('geeft de noot in een donker rapport een gedempte kleur', () => {
      expect(rapport('HO', metTitel('HO', { subtitle: { text: noot } }))).toMatch(/html\.dark \.vis-noot\{color:#9CA3AF\}/)
    })
  })

  describe('punt 2: jaartallen niet gekanteld', () => {
    const jaren = (x, extra = {}) => ({
      data: [{ type: 'scatter', mode: 'lines', x, y: x.map((_, i) => i) }],
      layout: { title: { text: 'T' }, xaxis: { type: 'category', categoryorder: 'category ascending', ...extra } },
    })
    const tien = Array.from({ length: 10 }, (_, i) => 2015 + i)

    it('toont op een telefoon om het andere jaar een label, met het laatste jaar erbij', () => {
      expect(getekend(rapport('G', jaren(tien)), 390).layout.xaxis).toMatchObject({ tickmode: 'linear', tick0: 1, dtick: 2, type: 'category' })
      const schooljaren = ["2019/'20", "2020/'21", "2021/'22", "2022/'23", "2023/'24", "2024/'25", "2025/'26"]
      expect(getekend(rapport('G', jaren(schooljaren)), 390).layout.xaxis).toMatchObject({ tickmode: 'linear', tick0: 0, dtick: 2 })
    })

    it('slaat meer jaren over naarmate er meer zijn', () => {
      const twintig = Array.from({ length: 20 }, (_, i) => `${2005 + i}/${String(6 + i).padStart(2, '0')}`)
      const { xaxis } = getekend(rapport('G', jaren(twintig)), 390).layout
      expect(xaxis.dtick).toBeGreaterThan(2)
      expect((twintig.length - 1 - xaxis.tick0) % xaxis.dtick).toBe(0)
    })

    it('laat weinig jaren, namen, een breed scherm en een eigen tickkeuze met rust', () => {
      expect(getekend(rapport('G', jaren([2023, 2024, 2025])), 390).layout.xaxis).not.toHaveProperty('dtick')
      const namen = ['Avans', 'Fontys', 'HAN', 'HvA', 'HR', 'HU', 'Saxion', 'Windesheim', 'Zuyd', 'Inholland']
      expect(getekend(rapport('G', jaren(namen)), 390).layout.xaxis).not.toHaveProperty('dtick')
      expect(getekend(rapport('G', jaren(tien)), 1024).layout.xaxis).not.toHaveProperty('dtick')
      expect(getekend(rapport('G', jaren(tien, { tickvals: [2015, 2024] })), 390).layout.xaxis).not.toHaveProperty('dtick')
    })
  })

  describe('punt 3 en 4: het plotvlak groeit mee', () => {
    const lijn = { data: [{ type: 'scatter', mode: 'lines', x: [1, 2], y: [1, 2] }], layout: { title: { text: 'T' } } }

    it('maakt een te laag plotvlak op een telefoon minstens 220 px hoog', async () => {
      const seen = await runPageNaTekenen(rapport('G', lijn), { plotH: 159 })
      expect(seen.errors).toEqual([])
      expect(seen.relayout).toEqual([{ height: 420 + 220 - 159 }])
      expect(seen.height).toBe(`${420 + 220 - 159}px`)
    })

    it('laat een plotvlak dat hoog genoeg is, en een breed scherm, met rust', async () => {
      expect((await runPageNaTekenen(rapport('G', lijn), { plotH: 240 })).relayout).toEqual([])
      expect((await runPageNaTekenen(rapport('G', lijn), { width: 1024, plotH: 120 })).relayout).toEqual([])
    })

    it('geeft elke rij liggende staven ruimte voor de langste afgebroken naam', async () => {
      const namen = Array.from({ length: 12 }, (_, i) => (i === 3 ? 'HAN University of Applied Sciences' : `Hogeschool ${i}`))
      const staven = {
        data: [{ type: 'bar', orientation: 'h', x: namen.map((_, i) => i), y: namen }],
        layout: { title: { text: 'T' }, yaxis: { autorange: 'reversed', automargin: true }, height: 466 },
      }
      // Twaalf rijen van twee regels: 12 × (2 × 14 + 4) = 384 px plotvlak.
      const seen = await runPageNaTekenen(rapport('G', staven), { plotH: 300 })
      expect(seen.errors).toEqual([])
      expect(seen.relayout).toEqual([{ height: 420 + 384 - 300 }])
    })
  })

  it('maakt waardelabels op een telefoon even groot als de ticks', () => {
    const fig = { data: [{ type: 'scatter', mode: 'lines+text', x: [1, 2], y: [1, 2], text: ['1', '2'] }, { type: 'scatter', x: [1, 2], y: [2, 3] }], layout: {} }
    const { data } = getekend(rapport('G', fig), 390)
    expect(data[0].textfont).toEqual({ size: 11 })
    expect(data[1]).not.toHaveProperty('textfont')
    expect(getekend(rapport('G', fig), 1024).data).toEqual(fig.data)
  })
})

// #651: de afrondingsnoot stond als ondertitel van 11 px in de figuur, of (titel gelijk aan de kop) als tekst boven de
// grafiek. Nu altijd als tekstregel onder de grafiek, vóór de bronregel; de figuur zelf draagt hem niet meer.
describe('afrondingsnoot onder een rapportgrafiek (#651)', () => {
  const NOOT = 'De aantallen zijn door CBS afgerond op 10-tallen: een som, verschil of percentage daarvan is niet exact.'
  const BRON = { bron: 'CBS', dataset: '85423NED', tekst: 'CBS · Hoger onderwijs; ingeschrevenen (85423NED)' }
  const figuur = (titel, meta = { afrondingsnoot: NOOT }) => ({
    data: [{ type: 'bar', x: ['2023', '2024'], y: [1, 2] }],
    layout: { title: { text: titel, font: { size: 16, color: '#222' } }, margin: { t: 60 }, meta },
  })
  const rapport = (kop, fig) => buildReportHtml({ ...fullSpec, visualisaties: [{ titel: kop, figure_json: JSON.stringify(fig), bron: BRON }] })
  const naGrafiek = new RegExp(`</script>\\s*<p class="vis-noot">${NOOT}</p>\\s*<p class="vis-bron">`)

  it('zet de noot na de grafiek en vóór de bronregel als de figuurtitel gelijk is aan de kop', () => {
    const html = rapport('Ingeschrevenen HO', figuur('Ingeschrevenen HO'))
    expect(html).toMatch(naGrafiek)
    expect(html.match(/class="vis-noot"/g)).toHaveLength(1)
    const seen = runPage(html)
    expect(seen.errors).toEqual([])
    expect(seen.plots[0][2]).not.toHaveProperty('title')
  })

  it('doet hetzelfde als de figuurtitel blijft staan', () => {
    const html = rapport('Ingeschrevenen', figuur('Ingeschrevenen HO per jaar'))
    expect(html).toMatch(naGrafiek)
    expect(runPage(html).plots[0][2].title).toEqual({ text: 'Ingeschrevenen HO per jaar', font: { size: 16, color: '#222' } })
  })

  it('haalt de ondertitel uit een bewaarde figuur, ook in het ingebedde figuurJSON', () => {
    const oud = figuur('Ingeschrevenen HO per jaar', undefined)
    oud.layout.title.subtitle = { text: 'De aantallen zijn door CBS afgerond op 10-tallen: een<br>som, verschil of percentage daarvan is niet exact.', font: { size: 11, color: '#666' } }
    oud.layout.margin = { t: 100 }
    for (const kop of ['Ingeschrevenen HO per jaar', 'Ingeschrevenen']) {
      const html = rapport(kop, oud)
      expect(html).toMatch(naGrafiek)
      expect(html).not.toContain('subtitle')
      for (const dark of [false, true]) {
        const seen = runPage(html, { dark })
        expect(seen.plots[0][2].title?.subtitle).toBeUndefined()
        expect(seen.plots[0][2].margin.t).toBeLessThanOrEqual(48)
      }
    }
  })

  it('zet de noot geëscaped neer', () => {
    const html = rapport('HO', figuur('HO', { afrondingsnoot: '<img src=x onerror=alert(1)> & "c"' }))
    expect(html).toContain('<p class="vis-noot">&lt;img src=x onerror=alert(1)&gt; &amp; &quot;c&quot;</p>')
    expect(runPage(html).images).toBe(0)
  })

  it('heeft zonder afronding geen noot', () => {
    expect(rapport('HO', figuur('HO', { data: [] }))).not.toContain('class="vis-noot"')
    expect(buildReportHtml(fullSpec)).not.toContain('class="vis-noot"')
  })

  it('geeft de noot de maat van de bronregel, afbreken in lange woorden en een donkere regel', () => {
    const html = rapport('HO', figuur('HO'))
    const regel = sel => html.match(new RegExp(`\\n\\s*\\${sel}\\{([^}]*)\\}`))?.[1] ?? ''
    expect(regel('.vis-noot')).toContain('font-size:.8rem')
    expect(regel('.vis-bron')).toContain('font-size:.8rem')
    expect(regel('.vis-noot')).toContain('margin-top:8px')
    expect(html).toMatch(/[,\n ]\.vis-noot,[^{]*\{overflow-wrap:anywhere\}/)
    expect(html).toMatch(/html\.dark \.vis-noot\{color:#9CA3AF\}/)
    expect(html).toMatch(/html:not\(\.light\) \.vis-noot\{color:#9CA3AF\}/)
  })
})

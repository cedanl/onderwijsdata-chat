import { describe, it, expect } from 'vitest'
import { JSDOM, VirtualConsole } from 'jsdom'
import { buildReportHtml } from '../reportHtml.js'
import { buildDashboardHtml } from '../dashboardHtml.js'
import { PLOTLY_URL } from '../plotlyBron'

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

describe('buildReportHtml', () => {
  // CH-34: the export's own 48 px top margin put a title note over the plot.
  it('keeps the top margin of a chart with a note under its title', () => {
    const layout = { title: { text: 'HO', subtitle: { text: 'Afgerond op 10-tallen' } }, margin: { t: 100 } }
    const spec = { ...fullSpec, visualisaties: [{ titel: 'HO', figure_json: JSON.stringify({ data: [], layout }) }] }
    expect(buildReportHtml(spec)).toContain('margin:{t:100,')
    expect(buildReportHtml(fullSpec)).toContain('margin:{t:48,')
  })

  // Horizontal bars bring their own height; the fixed 360 px squashed 18 universities.
  it('gives a chart the height it brings, and 360 px otherwise', () => {
    const spec = { ...fullSpec, visualisaties: [{ titel: 'WO', figure_json: JSON.stringify({ data: [], layout: { height: 526 } }) }] }
    expect(buildReportHtml(spec)).toContain('style="height:526px"')
    expect(buildReportHtml(fullSpec)).toContain('style="height:360px"')
  })

  // On a phone two nested card paddings left the chart 260 px; long names fell off the left.
  it('gives a chart the full card width on a phone', () => {
    const html = buildReportHtml(fullSpec)
    const phone = html.slice(html.indexOf('@media(max-width:640px)'))
    expect(phone.slice(0, phone.indexOf('}}') + 2)).toContain('.vis .card{padding:0}')
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

// Loads generated HTML in a fresh DOM that runs its inline scripts, with Plotly, the
// dialogs and matchMedia stubbed, and records what the page did. `dark` answers the
// prefers-color-scheme query.
function runPage(html, { dark = false } = {}) {
  const seen = { dialogs: [], plots: [], errors: [] }
  const virtualConsole = new VirtualConsole()
  virtualConsole.on('jsdomError', err => seen.errors.push(err.message))
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    virtualConsole,
    beforeParse(window) {
      for (const name of ['alert', 'confirm', 'prompt']) window[name] = (...args) => seen.dialogs.push([name, ...args])
      window.matchMedia = () => ({ matches: dark })
      window.Plotly = { newPlot: (...args) => seen.plots.push(args) }
    },
  })
  seen.images = dom.window.document.querySelectorAll('img').length
  dom.window.close()
  return seen
}

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

// WCAG relative luminance and contrast ratio of #RRGGBB colours.
function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// The light colours tools/plot.py bakes into a figure stayed in the dark report (#567).
describe('chart colours in a dark report (#567)', () => {
  const CARD = '#1F2937'
  const PLOT_BG = '#111827'
  const axis = { showgrid: true, gridcolor: '#f0f0f0', linecolor: '#ccc', zeroline: false }
  const layout = {
    title: {
      text: 'Instroom per jaar', font: { size: 16, color: '#222' }, yref: 'container', y: 0.98,
      subtitle: { text: 'Afgerond op 10-tallen', font: { size: 11, color: '#666' } },
    },
    xaxis: { ...axis, title: { text: 'Jaar' }, type: 'category' },
    yaxis: { ...axis, title: { text: 'Aantal' }, tickformat: ',d' },
    legend: { bgcolor: 'rgba(255,255,255,0.8)', bordercolor: '#ddd', borderwidth: 1, orientation: 'h' },
    margin: { t: 100 },
  }
  const data = [
    { type: 'bar', name: 'A', x: ['2023'], y: [1], marker: { color: '#0072B2' } },
    { type: 'bar', name: 'B', x: ['2023'], y: [2], marker: { color: '#000000' } },
    { type: 'scatter', name: 'C', x: ['2023'], y: [3], line: { color: '#000000', width: 2 } },
    { type: 'bar', name: 'D', x: ['2023'], y: [4], marker: { color: ['#B0B0B0', '#000', 'black'] } },
    { type: 'pie', labels: ['p', 'q', 'r'], values: [1, 2, 3], marker: { colors: ['#0072B2', '#F0E442', '#000000'] } },
  ]
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

  it('gives title, subtitle, grid, axis lines and legend dark colours', () => {
    const { layout: l } = plotted(figure, true)
    expect(l.title.font.color).not.toBe('#222')
    expect(l.title.subtitle.font.color).not.toBe('#666')
    expect(contrast(l.title.font.color, CARD)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(l.title.subtitle.font.color, CARD)).toBeGreaterThanOrEqual(4.5)
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
    expect(l.title).toMatchObject({ text: 'Instroom per jaar', yref: 'container', y: 0.98, font: { size: 16 } })
    expect(l.title.subtitle).toMatchObject({ text: 'Afgerond op 10-tallen', font: { size: 11 } })
    expect(l.xaxis).toMatchObject({ title: { text: 'Jaar' }, type: 'category', showgrid: true, zeroline: false })
    expect(l.yaxis).toMatchObject({ title: { text: 'Aantal' }, tickformat: ',d' })
    expect(l.legend).toMatchObject({ orientation: 'h', borderwidth: 1 })
    expect(l.plot_bgcolor).toBe(PLOT_BG)
    expect(l.margin.t).toBe(100)
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
      margin: { t: 100, r: 24, b: 48, l: 60 },
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

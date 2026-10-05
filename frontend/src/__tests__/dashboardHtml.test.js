// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { buildDashboardHtml, workbookHtml, workbookFilename } from '../dashboardHtml'

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

  it('laadt Plotly één keer en tekent elke grafiek', () => {
    expect(html.match(/cdn\.plot\.ly/g)).toHaveLength(1)
    expect(html).toContain("Plotly.newPlot('fig0'")
  })

  it('laat geen script ontsnappen uit de grafiekdata', () => {
    expect(html).not.toContain('</script><script>alert(1)')
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

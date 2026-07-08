import { describe, it, expect } from 'vitest'
import { parseTables, buildDashboardHtml, buildChartSpecs } from '../dashboardHtml.js'

describe('parseTables', () => {
  it('extracts a markdown table', () => {
    const md = `| Jaar | Studenten |
|------|-----------|
| 2020 | 1200 |
| 2021 | 1350 |`
    const tables = parseTables(md)
    expect(tables).toHaveLength(1)
    expect(tables[0].headers).toEqual(['Jaar', 'Studenten'])
    expect(tables[0].rows).toHaveLength(2)
    expect(tables[0].rows[0]).toEqual(['2020', '1200'])
  })

  it('returns empty array for text without tables', () => {
    expect(parseTables('Geen tabel hier')).toEqual([])
  })

  it('handles multiple tables', () => {
    const md = `| A | B |
|---|---|
| 1 | 2 |

Tekst ertussen

| C | D |
|---|---|
| 3 | 4 |`
    expect(parseTables(md)).toHaveLength(2)
  })
})

describe('buildDashboardHtml', () => {
  const tableContent = `Hier is de data:

| Jaar | Instroom | Uitstroom |
|------|----------|-----------|
| 2020 | 1200     | 800       |
| 2021 | 1350     | 900       |
| 2022 | 1500     | 1000      |`

  it('returns valid HTML with doctype', () => {
    const html = buildDashboardHtml('Test Dashboard', tableContent)
    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<title>Test Dashboard</title>')
  })

  it('includes Chart.js when tables have numeric data', () => {
    const html = buildDashboardHtml('Test', tableContent)
    expect(html).toContain('chart.js')
    expect(html).toContain('<canvas')
  })

  it('includes KPI cards with computed values', () => {
    const html = buildDashboardHtml('Test', tableContent)
    expect(html).toContain('kpi-val')
    expect(html).toContain('Hoogste waarde')
    expect(html).toContain('Laagste waarde')
  })

  it('includes instelling badge when provided', () => {
    const html = buildDashboardHtml('Test', tableContent, [], 'Hogeschool Utrecht')
    expect(html).toContain('Hogeschool Utrecht')
  })

  it('includes prose text outside tables', () => {
    const html = buildDashboardHtml('Test', tableContent)
    expect(html).toContain('Hier is de data')
  })

  it('handles content without tables gracefully', () => {
    const html = buildDashboardHtml('Test', 'Alleen tekst, geen tabellen.')
    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('Alleen tekst')
  })

  it('embeds plotly figures when provided', () => {
    const fakeFigure = '{"data":[],"layout":{}}'
    const html = buildDashboardHtml('Test', '', [fakeFigure])
    expect(html).toContain('plotly')
    expect(html).toContain('pf0')
  })

  it('escapes HTML in table data to prevent XSS', () => {
    const xssContent = `| Naam | Score |
|------|-------|
| <script>alert('xss')</script> | 100 |
| Normaal | 200 |`
    const html = buildDashboardHtml('Test', xssContent)
    expect(html).not.toContain("<script>alert('xss')</script>")
    expect(html).toContain('&lt;script&gt;')
  })

  it('escapes HTML in title and instelling', () => {
    const html = buildDashboardHtml('<img onerror=alert(1)>', 'tekst', [], '<b>evil</b>')
    expect(html).not.toContain('<img onerror=alert(1)>')
    expect(html).not.toContain('<b>evil</b>')
    expect(html).toContain('&lt;img onerror=alert(1)&gt;')
    expect(html).toContain('&lt;b&gt;evil&lt;/b&gt;')
  })
})

describe('buildChartSpecs', () => {
  it('handles table where all numeric columns are null/empty without crashing', () => {
    const tables = [{
      headers: ['Naam', 'Waarde'],
      rows: [
        ['A', ''],
        ['B', 'geen getal'],
        ['C', null],
      ]
    }]
    const specs = buildChartSpecs(tables)
    expect(specs).toEqual([])
  })

  it('parses Dutch thousand-separator numbers correctly', () => {
    const tables = [{
      headers: ['Provincie', 'Eerstejaars'],
      rows: [
        ['Zuid-Holland', '12.417'],
        ['Noord-Holland', '9.151'],
        ['Zeeland', '115'],
      ]
    }]
    const specs = buildChartSpecs(tables)
    expect(specs).toHaveLength(1)
    const data = specs[0].datasets[0].data
    expect(data[0]).toBe(12417)
    expect(data[1]).toBe(9151)
    expect(data[2]).toBe(115)
  })

  it('parses Dutch decimal comma correctly', () => {
    const tables = [{
      headers: ['Regio', 'Percentage'],
      rows: [
        ['Noord', '54,5'],
        ['Zuid', '1.234,56'],
      ]
    }]
    const specs = buildChartSpecs(tables)
    const data = specs[0].datasets[0].data
    expect(data[0]).toBeCloseTo(54.5)
    expect(data[1]).toBeCloseTo(1234.56)
  })

  it('formats KPI values in Dutch notation', () => {
    const content = `| Provincie | Eerstejaars |
|-----------|-------------|
| Zuid-Holland | 12.417 |
| Zeeland | 115 |`
    const html = buildDashboardHtml('Test', content)
    expect(html).toContain('12.417')
    expect(html).not.toMatch(/kpi-val[^<]*<[^>]*>12417</)
  })
})

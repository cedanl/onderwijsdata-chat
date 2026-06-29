import { describe, it, expect } from 'vitest'
import { parseTables, buildDashboardHtml } from '../dashboardHtml.js'

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
})

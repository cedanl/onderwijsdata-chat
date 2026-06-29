// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { saveWorkbook, getWorkbooks, deleteWorkbook } from '../workbooks.js'
import { buildDashboardHtml, parseTables } from '../dashboardHtml.js'

const SEED_ASSISTANT_CONTENT = `## Gediplomeerden per jaar — Hogeschool Utrecht

| Jaar | Hogeschool Utrecht | Universiteit Utrecht |
|------|-------------------|---------------------|
| 2019 | 7245              | 8120                |
| 2020 | 7510              | 8450                |
| 2021 | 7890              | 8780                |
| 2022 | 8120              | 9100                |
| 2023 | 8450              | 9350                |

De Hogeschool Utrecht laat een **stijgende trend** zien.

## Verdeling naar sector

| Sector | Gediplomeerden 2023 | Aandeel |
|--------|--------------------:|--------:|
| Economie | 2850 | 33.7% |
| Gezondheidszorg | 1920 | 22.7% |
| Techniek | 1350 | 16.0% |`

describe('dashboard save flow (end-to-end)', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('parseTables extracts tables from seed content', () => {
    const tables = parseTables(SEED_ASSISTANT_CONTENT)
    expect(tables.length).toBe(2)
    expect(tables[0].headers).toContain('Jaar')
    expect(tables[0].rows.length).toBe(5)
    expect(tables[1].headers).toContain('Sector')
    expect(tables[1].rows.length).toBe(3)
  })

  it('buildDashboardHtml generates valid HTML from seed content', () => {
    const html = buildDashboardHtml(
      'Test Dashboard',
      SEED_ASSISTANT_CONTENT,
      [],
      'Hogeschool Utrecht'
    )
    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<title>Test Dashboard</title>')
    expect(html).toContain('chart.js')
    expect(html).toContain('<canvas')
    expect(html).toContain('kpi-val')
    expect(html).toContain('Hogeschool Utrecht')
    expect(html.length).toBeGreaterThan(1000)
  })

  it('saveWorkbook stores the dashboard and getWorkbooks retrieves it', () => {
    const html = buildDashboardHtml('Test', SEED_ASSISTANT_CONTENT, [], 'HU')

    const result = saveWorkbook({
      title: 'Test Dashboard',
      description: 'Aangemaakt op 29 juni 2026',
      htmlContent: html,
    })

    expect(result.ok).toBe(true)
    expect(result.workbook).toBeDefined()
    expect(result.workbook.id).toBeTruthy()
    expect(result.workbook.htmlContent).toBe(html)
    expect(result.workbook.title).toBe('Test Dashboard')

    // Verify it's actually in localStorage
    const stored = getWorkbooks()
    expect(stored.length).toBe(1)
    expect(stored[0].id).toBe(result.workbook.id)
    expect(stored[0].title).toBe('Test Dashboard')
    expect(stored[0].htmlContent).toBe(html)
  })

  it('full flow: build HTML → save → retrieve → verify content', () => {
    const title = 'Hoeveel gediplomeerden levert Hogeschool Utrecht per jaa'
    const html = buildDashboardHtml(title, SEED_ASSISTANT_CONTENT, [], 'Hogeschool Utrecht')

    const result = saveWorkbook({
      title,
      description: 'Aangemaakt op 29 juni 2026',
      htmlContent: html,
    })
    expect(result.ok).toBe(true)

    // This is what handleSaved does: read from localStorage
    const workbooks = getWorkbooks()
    expect(workbooks.length).toBe(1)

    const wb = workbooks.find(w => w.id === result.workbook.id)
    expect(wb).toBeDefined()
    expect(wb.htmlContent).toContain('<!DOCTYPE html>')
    expect(wb.htmlContent).toContain('chart.js')
    expect(wb.htmlContent).toContain('kpi-val')
    expect(wb.htmlContent).toContain('Hogeschool Utrecht')
  })

  it('multiple dashboards accumulate in localStorage', () => {
    const html1 = buildDashboardHtml('Dash 1', SEED_ASSISTANT_CONTENT)
    const html2 = buildDashboardHtml('Dash 2', SEED_ASSISTANT_CONTENT)

    const r1 = saveWorkbook({ title: 'Dash 1', description: 'Test', htmlContent: html1 })
    const r2 = saveWorkbook({ title: 'Dash 2', description: 'Test', htmlContent: html2 })

    expect(r1.ok).toBe(true)
    expect(r2.ok).toBe(true)

    const all = getWorkbooks()
    expect(all.length).toBe(2)
    expect(all[0].title).toBe('Dash 1')
    expect(all[1].title).toBe('Dash 2')
  })

  it('deleteWorkbook removes the right workbook', () => {
    const html = buildDashboardHtml('To Delete', SEED_ASSISTANT_CONTENT)
    const r1 = saveWorkbook({ title: 'Keep', description: 'Test', htmlContent: html })
    const r2 = saveWorkbook({ title: 'To Delete', description: 'Test', htmlContent: html })

    deleteWorkbook(r2.workbook.id)

    const remaining = getWorkbooks()
    expect(remaining.length).toBe(1)
    expect(remaining[0].id).toBe(r1.workbook.id)
  })

  it('saved htmlContent renders iframe-compatible dashboard', () => {
    const html = buildDashboardHtml('Iframe Test', SEED_ASSISTANT_CONTENT, [], 'HU')
    const result = saveWorkbook({ title: 'Iframe Test', description: 'Test', htmlContent: html })
    const wb = getWorkbooks().find(w => w.id === result.workbook.id)

    // Verify the HTML is a complete standalone page that an iframe can render
    expect(wb.htmlContent).toMatch(/^<!DOCTYPE html>/)
    expect(wb.htmlContent).toContain('<html')
    expect(wb.htmlContent).toContain('</html>')
    expect(wb.htmlContent).toContain('<style>')
    expect(wb.htmlContent).toContain('<script')
    expect(wb.htmlContent).toContain('new Chart(')
  })
})

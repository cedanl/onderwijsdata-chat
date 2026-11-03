import { describe, it, expect } from 'vitest'
import { workbookHtml, workbookFilename } from '../workbookHtml'

describe('workbookHtml', () => {
  it('geeft een rapport zijn eigen HTML', () => {
    expect(workbookHtml({ title: 'R', htmlContent: '<html>rapport</html>' })).toBe('<html>rapport</html>')
  })

  it('heeft niets voor een ingebouwd dashboard', () => {
    expect(workbookHtml({ title: 'Mijn instelling', builtin: true })).toBeNull()
  })

  it('heeft niets voor een werkboek zonder HTML, zoals een dashboard uit de verwijderde dashboardbouwer (#765)', () => {
    expect(workbookHtml({ title: 'D', dashboardSpec: { figures_json: [] } })).toBeNull()
  })

  it('maakt een bestandsnaam van de titel', () => {
    expect(workbookFilename({ title: 'Instroom HU 2023/24' })).toBe('Instroom_HU_2023_24.html')
    expect(workbookFilename({})).toBe('rapport.html')
  })
})

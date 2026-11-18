// @vitest-environment jsdom
// #1038: de server leest het bewaarde rapport voor "Download als Word" met een Python-tweeling van rapportUitHtml.js
// (tools/rapport_docx/uit_html.py). Beide lezers krijgen hetzelfde vaste rapport en moeten er hetzelfde uit halen:
// tests/test_rapport_docx_uit_html.py toetst de Python-kant tegen dezelfde twee bestanden.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { rapportUitHtml } from '../rapportUitHtml'

const fixture = naam => readFileSync(join(__dirname, '..', '..', '..', 'tests', 'fixtures', 'rapport_docx', naam), 'utf-8')

describe('het vaste rapport voor de Word-export', () => {
  it('leest rapportUitHtml.js zoals de verwachting die ook de server-test gebruikt', () => {
    expect(rapportUitHtml(fixture('rapport.html'))).toEqual(JSON.parse(fixture('rapport.json')))
  })
})

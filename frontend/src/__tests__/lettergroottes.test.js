// #613 (mobiel N5): op een telefoon was de antwoordtekst 14,4 px en zaten de kleinste lagen (code, citaatpopover,
// chips, labels) op 10,5–12 px. Besluit 19-10: antwoordtekst 16 px, ondergrens 12,5 px; code mag 11 px en de
// rapportmetadata op /rapporten blijft bewust klein. Gemeten op 390 px in de MR; dit legt de regels vast.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')
const telefoon = css.slice(css.indexOf('Lettergroottes op een telefoon (#613'))
const blok = telefoon.match(/@media \(max-width: 600px\)\s*{[\s\S]*?\n}/)?.[0]

describe('lettergroottes op een telefoon (#613)', () => {
  it('zet de antwoordtekst op 16 px', () => {
    expect(blok).toMatch(/\.message-bubble\s*{\s*font-size:\s*16px/)
  })

  it('geeft de kleine lagen 12,5 px en code 11 px via de variabelen', () => {
    expect(blok).toContain('--font-klein: 12.5px')
    expect(blok).toContain('--font-label: 12.5px')
    expect(blok).toContain('--font-code: 11px')
    for (const laag of ['.suggested-btn', '.citatie-details', '.reasoning-step-code summary', '.question-buttons-kop', '.data-export-btn', '.message-model', '.settings-modal label']) {
      expect(blok, laag).toContain(laag)
    }
    expect(blok).toMatch(/font-size:\s*12\.5px/)
  })

  // #639: de herhaalmeting op 390 px vond nog lagen met een eigen font-size buiten de variabelen (10,5–12,3 px).
  it('brengt ook de lagen met een eigen font-size op 12,5 px', () => {
    for (const laag of ['.sidebar-section-title', '.suggested-category-btn', '.new-chat-btn', '.model-picker-provider', '.navbar-menu-sub',
      '.wb-gallery-sub', '.wb-gallery-search-label', '.wb-gallery-feedback', '.wb-gallery-leeg-tip', '.privacy-link',
      '.history-btn-title', '.history-btn-date']) {
      expect(blok, laag).toContain(laag)
    }
  })

  // #650: de meting op 390 px (licht en donker, touch) na #639 vond nog "Meer laden", de noot in het ⋯-menu, de
  // homepage (sectielabel, disclaimer, licentie, footerlinks) en op /dashboards de nieuw-kaart en de voorbeeldkaarten.
  it('brengt de restlagen van #650 op 12,5 px', () => {
    for (const laag of ['.history-more-btn', '.navbar-meer-noot', '.section-label', '.home-disclaimer', '.home-licentie',
      '.sources-link', '.wb-new-card small', '.wb-builtin-badge', '.wb-builtin-instelling']) {
      expect(blok, laag).toContain(laag)
    }
  })

  it('verbergt de Ctrl K-hint op een aanraakscherm, ook breder dan 768 px (#650)', () => {
    expect(css).toMatch(/@media \(hover: none\), \(pointer: coarse\)\s*{\s*\.navbar-zoek-hint\s*{\s*display:\s*none/)
  })

  it('houdt de variabelen op desktop op de oude maten', () => {
    expect(css).toMatch(/:root\s*{[\s\S]*?--font-klein:\s*\.75rem;[\s\S]*?--font-label:\s*\.8rem;[\s\S]*?--font-code:\s*\.7rem;/)
  })

  it('laat de rapportmetadata op /rapporten bewust klein', () => {
    expect(blok).not.toContain('.wb-card-date')
    expect(blok).not.toContain('.wb-card-desc')
  })
})

// #663: de laatste lagen uit de metingen van #613/#650 zitten alleen op desktop (> 768 px of > 1024 px) en hadden
// een eigen, kleinere maat: het label "Zoeken" (12 px), de instelling en accountnaam in de profielknop (inline
// 11,25 en 10,8 px) en de disclaimer onder het invoerveld (10,8 px). Ze krijgen 12,5 px op elke breedte.
describe('lagen op desktop onder 12,5 px (#663)', () => {
  const zonderCommentaar = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const regel = (selector) => {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return zonderCommentaar.match(new RegExp(`\\n${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? ''
  }
  const nav = readFileSync(join(import.meta.dirname, '..', 'components', 'Nav.jsx'), 'utf8')

  for (const selector of ['.navbar-zoek-btn', '.chat-disclaimer', '.navbar-profile-instelling', '.navbar-profile-naam']) {
    it(`geeft ${selector} 12,5 px`, () => {
      expect(regel(selector)).toMatch(/font-size:\s*12\.5px/)
    })
  }

  it('houdt kleur, gewicht en regelhoogte van de profielknop gelijk', () => {
    expect(regel('.navbar-profile-instelling')).toMatch(/font-weight:\s*600/)
    expect(regel('.navbar-profile-instelling')).toMatch(/color:\s*var\(--gray-700\)/)
    expect(regel('.navbar-profile-instelling')).toMatch(/line-height:\s*1\.2/)
    expect(regel('.navbar-profile-naam')).toMatch(/color:\s*var\(--muted-text\)/)
    expect(regel('.navbar-profile-naam')).toMatch(/line-height:\s*1\.2/)
  })

  // De scan op 390 px vond ook de verbindingsmelding (10,8 px) zolang de socket nog niet open is.
  it('brengt de verbindingsmelding op een telefoon op 12,5 px', () => {
    expect(blok).toContain('.ws-reconnecting')
  })

  it('zet geen lettergrootte meer inline in de profielknop', () => {
    expect(nav).not.toMatch(/fontSize:\s*'\.7[25]rem'/)
    expect(nav).toContain('className="navbar-profile-instelling"')
    expect(nav).toContain('className="navbar-profile-naam"')
  })
})

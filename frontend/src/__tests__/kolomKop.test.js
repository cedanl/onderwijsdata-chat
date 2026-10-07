// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import KolomKop, { kolomLabel } from '../components/KolomKop'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

describe('kolomLabel (#222)', () => {
  it('maakt van een ruwe bronkolom een leesbaar label', () => {
    expect(kolomLabel('AANTAL_EERSTEJAARS_INGESCHREVENEN')).toBe('Aantal eerstejaars ingeschrevenen')
  })

  it('houdt afkortingen in hoofdletters', () => {
    expect(kolomLabel('BRIN_NUMMER_ACTUEEL')).toBe('BRIN nummer actueel')
    expect(kolomLabel('OPLEIDINGSVORM_BOL_BBL')).toBe('Opleidingsvorm BOL BBL')
    expect(kolomLabel('CROHO_ONDERDEEL')).toBe('CROHO onderdeel')
  })

  it('laat een kop die al leesbaar is staan', () => {
    for (const kop of ['Schooljaar', 'Aantal studenten', 'BRIN', '2024/25']) {
      expect(kolomLabel(kop)).toBe(kop)
    }
  })

  // Zelfde regel als tools/kolomlabel.py voor de grafiekassen (#418).
  it('maakt ook een los woord in hoofdletters leesbaar, vanaf vier letters', () => {
    expect(kolomLabel('OPLEIDINGSVORM')).toBe('Opleidingsvorm')
    expect(kolomLabel('STUDIEJAAR')).toBe('Studiejaar')
    for (const code of ['VT', 'MAN', 'WO', 'CROHO']) expect(kolomLabel(code)).toBe(code)
  })

  it('noemt een labelkolom naar wat hij toont', () => {
    expect(kolomLabel('STUDIEJAAR_LABEL')).toBe('Studiejaar')
    expect(kolomLabel('Perioden_label')).toBe('Perioden')
  })
})

describe('KolomKop in een markdowntabel', () => {
  let root
  let container

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('toont het label en bewaart de bronnaam als title', () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    const markdown = '| INSTELLINGSNAAM_ACTUEEL | Aantal |\n|---|---|\n| HAN | 4.147 |'
    act(() => root.render(createElement(ReactMarkdown, { remarkPlugins: [remarkGfm], components: { th: KolomKop } }, markdown)))

    const [eerste, tweede] = container.querySelectorAll('th')
    expect(eerste.textContent).toBe('Instellingsnaam actueel')
    expect(eerste.getAttribute('title')).toBe('INSTELLINGSNAAM_ACTUEEL')
    expect(tweede.textContent).toBe('Aantal')
    expect(tweede.hasAttribute('title')).toBe(false)
  })
})

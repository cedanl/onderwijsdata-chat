// @vitest-environment jsdom
// #1038: "Download als Word" stuurt de grafieken van het rapport als PNG mee. Het rapport staat in een sandbox-frame
// met een opaque origin (#634), dus een script van de app in een eigen grafiekframe maakt ze met Plotly.toImage en
// stuurt ze met postMessage terug; de app neemt alleen het antwoord van dat frame.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { JSDOM } from 'jsdom'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useReportFrame } from '../hooks/useReportFrame'
import { FRAME_BRON } from '../reportFrame'
import { PRINT_BREEDTE } from '../reportHtml'
import {
  GRAFIEK_VRAAG, MAX_GRAFIEKEN, MAX_GRAFIEK_BYTES, grafiekAntwoord, grafiekFormulier, metGrafiekVraag, vraagGrafieken,
} from '../rapportGrafieken'

const PNG = 'data:image/png;base64,iVBORw0KGgo='

// Het script van de app in een echt document, met een nep-Plotly. Een jsdom-venster op het hoogste niveau is zijn
// eigen parent: een bericht met dat venster als bron komt dus van "de app", en het antwoord gaat naar hetzelfde venster.
// jsdom zet bij postMessage geen bron, dus het bericht gaat hier als MessageEvent met een bron.
function frameMet(lichaam, toImage) {
  const dom = new JSDOM(metGrafiekVraag(`<html><body>${lichaam}</body></html>`), {
    runScripts: 'dangerously',
    beforeParse(window) { window.Plotly = { toImage } },
  })
  return dom.window
}

const stuur = (win, data, source = win) => win.dispatchEvent(new win.MessageEvent('message', { data, source }))

function vraag(win, data) {
  return new Promise(resolve => {
    win.addEventListener('message', e => { if (e.data?.grafieken) resolve(e.data) })
    stuur(win, data)
  })
}

describe('het script in het grafiekframe', () => {
  it('geeft per visualisatie een PNG, in de volgorde van het rapport, op A4-breedte en licht', async () => {
    const toImage = vi.fn((el, opties) => Promise.resolve(`${PNG}${el.id}${opties.width}`))
    const win = frameMet(
      '<div class="vis"><div id="a" class="js-plotly-plot"></div></div><div class="vis"><p>geen grafiek</p></div>'
        + '<div class="vis"><div id="b" class="js-plotly-plot"></div></div>',
      toImage,
    )
    const antwoord = await vraag(win, { bron: FRAME_BRON, vraag: GRAFIEK_VRAAG, id: 'v1' })
    expect(antwoord).toEqual({ bron: FRAME_BRON, id: 'v1', grafieken: [`${PNG}a${PRINT_BREEDTE}`, null, `${PNG}b${PRINT_BREEDTE}`] })
    expect(toImage.mock.calls[0][1]).toMatchObject({ format: 'png', scale: 2, width: PRINT_BREEDTE })
  })

  it('geeft null voor een grafiek die niet lukt', async () => {
    const win = frameMet('<div class="vis"><div class="js-plotly-plot"></div></div>', () => Promise.reject(new Error('x')))
    expect((await vraag(win, { bron: FRAME_BRON, vraag: GRAFIEK_VRAAG, id: 'v2' })).grafieken).toEqual([null])
  })

  it('negeert een bericht zonder de bron of de vraag van de app', async () => {
    const toImage = vi.fn(() => Promise.resolve(PNG))
    const win = frameMet('<div class="vis"><div class="js-plotly-plot"></div></div>', toImage)
    stuur(win, { vraag: GRAFIEK_VRAAG, id: 'x' })
    stuur(win, { bron: FRAME_BRON, vraag: 'iets anders', id: 'x' })
    // Ook de goede vraag telt niet als hij niet van de parent komt (hier: zonder bron).
    stuur(win, { bron: FRAME_BRON, vraag: GRAFIEK_VRAAG, id: 'x' }, null)
    await new Promise(r => setTimeout(r, 20))
    expect(toImage).not.toHaveBeenCalled()
  })
})

describe('grafiekAntwoord', () => {
  const frame = {}
  const bericht = (data, source = frame) => ({ data, source })

  it('neemt alleen het antwoord van het eigen frame op de eigen vraag, en alleen PNG-data-URLs', () => {
    expect(grafiekAntwoord(bericht({ bron: FRAME_BRON, id: 'v', grafieken: [PNG, null, 'data:text/html,x', 3] }), frame, 'v'))
      .toEqual([PNG, null, null, null])
    expect(grafiekAntwoord(bericht({ bron: FRAME_BRON, id: 'v', grafieken: [PNG] }, {}), frame, 'v')).toBeNull()
    expect(grafiekAntwoord(bericht({ bron: FRAME_BRON, id: 'ander', grafieken: [PNG] }), frame, 'v')).toBeNull()
    expect(grafiekAntwoord(bericht({ bron: 'iets', id: 'v', grafieken: [PNG] }), frame, 'v')).toBeNull()
    expect(grafiekAntwoord(bericht({ bron: FRAME_BRON, id: 'v', grafieken: 'x' }), frame, 'v')).toBeNull()
    expect(grafiekAntwoord(bericht({ bron: FRAME_BRON, id: 'v', grafieken: [PNG] }), null, 'v')).toBeNull()
  })
})

describe('vraagGrafieken', () => {
  afterEach(() => { document.body.innerHTML = '' })

  it('maakt een onzichtbaar frame met alleen allow-scripts, vraagt na het laden, en ruimt het op', async () => {
    const belofte = vraagGrafieken('<p>rapport</p>', { timeoutMs: 1000 })
    const frame = document.querySelector('iframe')
    expect(frame.getAttribute('sandbox')).toBe('allow-scripts')
    expect(frame.getAttribute('aria-hidden')).toBe('true')
    expect(frame.style.left).toBe('-10000px')
    const postMessage = vi.spyOn(frame.contentWindow, 'postMessage')
    frame.dispatchEvent(new Event('load'))
    const [vraagBericht] = postMessage.mock.calls[0]
    expect(vraagBericht).toMatchObject({ bron: FRAME_BRON, vraag: GRAFIEK_VRAAG })
    // Een bericht van een ander venster telt niet; het antwoord van het frame wel.
    window.dispatchEvent(new MessageEvent('message', { data: { bron: FRAME_BRON, id: vraagBericht.id, grafieken: ['x'] }, source: window }))
    window.dispatchEvent(new MessageEvent('message', { data: { bron: FRAME_BRON, id: vraagBericht.id, grafieken: [PNG] }, source: frame.contentWindow }))
    expect(await belofte).toEqual([PNG])
    expect(document.querySelector('iframe')).toBeNull()
  })

  it('gaat zonder grafieken verder als het frame niet antwoordt', async () => {
    expect(await vraagGrafieken('<p>rapport</p>', { timeoutMs: 10 })).toEqual([])
    expect(document.querySelector('iframe')).toBeNull()
  })
})

describe('grafiekFormulier', () => {
  const dataUrl = bytes => `data:image/png;base64,${btoa('x'.repeat(bytes))}`

  it('zet elke grafiek onder grafiek-<plek>', () => {
    const { form, mee } = grafiekFormulier([dataUrl(10), null, dataUrl(20)])
    expect(mee).toBe(2)
    expect([...form.keys()]).toEqual(['grafiek-0', 'grafiek-2'])
    expect(form.get('grafiek-2').type).toBe('image/png')
    expect(form.get('grafiek-2').size).toBe(20)
  })

  it('blijft binnen de grenzen van de server', () => {
    expect(grafiekFormulier(Array.from({ length: MAX_GRAFIEKEN + 3 }, () => dataUrl(10))).mee).toBe(MAX_GRAFIEKEN)
    expect(grafiekFormulier([dataUrl(MAX_GRAFIEK_BYTES + 1), dataUrl(10)]).mee).toBe(1)
    expect(grafiekFormulier(Array.from({ length: 3 }, () => dataUrl(1.5 * 1024 * 1024))).mee).toBe(2)
    expect(grafiekFormulier(['data:image/png;base64,%%%']).mee).toBe(0)
  })
})

describe('het rapport voor het grafiekframe (useReportFrame)', () => {
  async function grafiekDocVan(html, mode) {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true
    let gezien
    function Kijker() { gezien = useReportFrame(html, mode).grafiekDoc; return null }
    const root = createRoot(document.createElement('div'))
    await act(async () => root.render(createElement(Kijker)))
    await act(async () => root.unmount())
    return gezien
  }

  it('is licht, ook in het donkere thema, met de policy van de viewer en het script van de app', async () => {
    const doc = await grafiekDocVan('<html><body><p>rapport</p></body></html>', 'dark')
    expect(doc).toMatch(/^<!DOCTYPE html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; /)
    expect(doc).toContain("connect-src 'none'")
    expect(doc).toContain('<html class="light">')
    expect(doc).not.toContain('class="dark"')
    expect(doc.endsWith(metGrafiekVraag(''))).toBe(true)
  })

  it('bestaat niet zonder rapport', async () => {
    expect(await grafiekDocVan(null, 'light')).toBeNull()
  })
})

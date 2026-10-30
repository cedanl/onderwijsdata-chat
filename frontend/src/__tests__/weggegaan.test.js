// @vitest-environment jsdom
// #772: de markering van een antwoord of rapport dat stopte omdat de gebruiker wegging, en hoe die een herstel overleeft.
import { describe, it, expect, beforeEach } from 'vitest'
import { eindigtWeggegaan, markeerWeggegaan, RAPPORT_WEGGEGAAN } from '../weggegaan'
import { buildHistory } from '../hooks/useChat'
import { loadCurrentChat, persistCurrentChat } from '../conversationStore'

const VRAAG = { id: 1, role: 'user', content: 'Hoeveel studenten?', done: true }

describe('markeerWeggegaan (#772)', () => {
  it('sluit het lopende antwoord af als gestopt, met de tekst uit de deltabuffer', () => {
    const [, antwoord] = markeerWeggegaan([VRAAG, { id: 2, role: 'assistant', content: 'Het aantal', done: false }], { deeltekst: ' is' })
    expect(antwoord).toMatchObject({ id: 2, content: 'Het aantal is', done: true, stopped: true, weggegaan: true })
    expect(antwoord.interrupted).toBeUndefined()
  })

  it('geeft een antwoord zonder eigen tekst zijn laatste tussentekst terug', () => {
    const [, antwoord] = markeerWeggegaan([VRAAG, { id: 2, role: 'assistant', content: '', tussentekst: ['Ik zoek de dataset op.'], done: false }])
    expect(antwoord.content).toBe('Ik zoek de dataset op.')
  })

  it('zet de markering in een leeg antwoord als er nog geen antwoord was', () => {
    const berichten = markeerWeggegaan([VRAAG], { id: 9 })
    expect(berichten).toHaveLength(2)
    expect(berichten[1]).toMatchObject({ id: 9, role: 'assistant', content: '', done: true, weggegaan: true })
  })

  it('voegt bij een rapport een eigen regel toe met de weg terug, geen modelbeurt', () => {
    const klaar = { id: 2, role: 'assistant', content: 'Antwoord', done: true }
    const berichten = markeerWeggegaan([VRAAG, klaar], { rapport: true, id: 3 })
    expect(berichten.slice(0, 2)).toEqual([VRAAG, klaar])
    expect(berichten[2]).toMatchObject({ content: RAPPORT_WEGGEGAAN, isError: true, herstel: 'rapport', weggegaan: true })
    expect(buildHistory(berichten)).toHaveLength(2)
  })

  it('gaat als afgebroken beurt naar de server, zodat die de beurt afsluit (#548)', () => {
    const berichten = markeerWeggegaan([VRAAG])
    expect(buildHistory(berichten).at(-1)).toEqual({ role: 'assistant', content: '', afgebroken: true })
  })
})

describe('eindigtWeggegaan (#772)', () => {
  it('kijkt over een grafiek van de gestopte run heen', () => {
    const berichten = [...markeerWeggegaan([VRAAG, { id: 2, role: 'assistant', content: 'x', done: false }]), { id: 3, role: 'assistant', figures: [{}], done: true }]
    expect(eindigtWeggegaan(berichten)).toBe(true)
  })

  it('is onwaar zodra er daarna verder gevraagd is', () => {
    expect(eindigtWeggegaan([...markeerWeggegaan([VRAAG]), { id: 4, role: 'user', content: 'En nu?', done: true }])).toBe(false)
    expect(eindigtWeggegaan([])).toBe(false)
  })
})

describe('herstel na verversen of terugkeer (#772)', () => {
  beforeEach(() => localStorage.clear())

  it('houdt de markering, ook van een leeg antwoord, en maakt er geen "Verbinding verbroken" van', () => {
    persistCurrentChat('g1', markeerWeggegaan([VRAAG], { id: 2 }))
    const { messages } = loadCurrentChat()
    expect(messages).toHaveLength(2)
    expect(messages[1]).toMatchObject({ weggegaan: true, stopped: true })
    expect(messages[1].interrupted).toBeUndefined()
  })
})

// @vitest-environment jsdom
// #709: a link /chat#vraag=… carries a question into the app. It is read once, cleaned and bounded, and leaves the
// address bar; in sessionStorage it survives the login, also the round trip via SRAM.
import { describe, it, expect, beforeEach } from 'vitest'
import { MAX_VOORGEVULDE_VRAAG, bewaarVraagUitUrl, neemVoorgevuldeVraag, schoonVraag, wachtVoorgevuldeVraag } from '../voorgevuldeVraag'
import { STORAGE_VOORGEVULDE_VRAAG } from '../constants'
import { clearLocalSessionData } from '../sessionData'

beforeEach(() => {
  sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})

describe('schoonVraag', () => {
  it('keeps an ordinary question as it is', () => {
    expect(schoonVraag('Hoeveel eerstejaars had het hbo in 2024?')).toBe('Hoeveel eerstejaars had het hbo in 2024?')
  })

  it('makes one line of it and trims it', () => {
    expect(schoonVraag('  Hoeveel\n\neerstejaars\t hbo?  ')).toBe('Hoeveel eerstejaars hbo?')
  })

  it('drops control characters, zero-width characters and bidi overrides', () => {
    expect(schoonVraag('mbo\u0000\u0007 diploma​‮⁦ 2024﻿')).toBe('mbo diploma 2024')
  })

  it('drops angle brackets, so no tag survives', () => {
    expect(schoonVraag('<img src=x onerror=alert(1)>Hoeveel mbo-studenten?</b>')).toBe('img src=x onerror=alert(1)Hoeveel mbo-studenten?/b')
  })

  it('cuts a long question at the limit, without splitting an emoji', () => {
    const lang = `${'a'.repeat(MAX_VOORGEVULDE_VRAAG - 1)}🎓🎓`
    const kort = schoonVraag(lang)
    expect(Array.from(kort)).toHaveLength(MAX_VOORGEVULDE_VRAAG)
    expect(kort.endsWith('🎓')).toBe(true)
  })

  it('is null for nothing, only spaces or no text', () => {
    expect(schoonVraag('')).toBeNull()
    expect(schoonVraag(' ​ \n ')).toBeNull()
    expect(schoonVraag(null)).toBeNull()
    expect(schoonVraag(42)).toBeNull()
  })
})

describe('bewaarVraagUitUrl', () => {
  it('takes the question out of the fragment and keeps the rest of the address', () => {
    window.history.replaceState({}, '', '/chat?x=1#vraag=Hoeveel%20mbo-studenten%3F&deel=2')

    bewaarVraagUitUrl()

    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/chat?x=1#deel=2')
    expect(sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)).toBe('Hoeveel mbo-studenten?')
  })

  it('leaves no hash behind when the question was all of the fragment', () => {
    window.history.replaceState({}, '', '/chat#vraag=hbo')
    bewaarVraagUitUrl()
    expect(window.location.href).toBe(`${window.location.origin}/chat`)
  })

  it('reads a + as a space, as Python urlencode writes it', () => {
    window.history.replaceState({}, '', '/chat#vraag=gediplomeerden+mbo')
    bewaarVraagUitUrl()
    expect(sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)).toBe('gediplomeerden mbo')
  })

  it('stores the cleaned question', () => {
    window.history.replaceState({}, '', `/chat#vraag=${encodeURIComponent('<b>wo</b>\ninstroom')}`)
    bewaarVraagUitUrl()
    expect(sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)).toBe('bwo/b instroom')
  })

  it('forgets an earlier question when the link carries an empty one', () => {
    sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, 'oud')
    window.history.replaceState({}, '', '/chat#vraag=')
    bewaarVraagUitUrl()
    expect(wachtVoorgevuldeVraag()).toBe(false)
  })

  it('does not read the query string, which reaches server and proxy logs', () => {
    window.history.replaceState({}, '', '/chat?vraag=hbo')
    bewaarVraagUitUrl()
    expect(wachtVoorgevuldeVraag()).toBe(false)
  })

  it('does nothing without the parameter', () => {
    sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, 'van de login')
    window.history.replaceState({}, '', '/#token=abc')
    bewaarVraagUitUrl()
    expect(window.location.hash).toBe('#token=abc')
    expect(sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)).toBe('van de login')
  })
})

describe('neemVoorgevuldeVraag', () => {
  it('gives the question once', () => {
    sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, 'Hoeveel hbo-studenten?')
    expect(wachtVoorgevuldeVraag()).toBe(true)
    expect(neemVoorgevuldeVraag()).toBe('Hoeveel hbo-studenten?')
    expect(wachtVoorgevuldeVraag()).toBe(false)
    expect(neemVoorgevuldeVraag()).toBeNull()
  })

  it('cleans what it reads, whoever wrote it', () => {
    sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, '<script>x</script>')
    expect(neemVoorgevuldeVraag()).toBe('scriptx/script')
  })

  it('survives the wipe at login', () => {
    sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, 'Hoeveel hbo-studenten?')
    clearLocalSessionData()
    expect(neemVoorgevuldeVraag()).toBe('Hoeveel hbo-studenten?')
  })
})

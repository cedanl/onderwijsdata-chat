// @vitest-environment jsdom
// #671: de app aanbieden voor het startscherm. Chromium geeft een beforeinstallprompt die we bewaren; iOS heeft er geen
// en krijgt uitleg; een geïnstalleerde app krijgt niets.
import { describe, it, expect, vi } from 'vitest'
import { installatieAanbod, isIos, isStandalone, startInstallatieAanbod, vraagInstallatie } from '../installeerApp'

describe('installatieAanbod', () => {
  it('biedt niets aan in een geïnstalleerde app, ook niet op iOS of met een prompt', () => {
    expect(installatieAanbod({ standalone: true, ios: true, heeftPrompt: true })).toBeNull()
  })
  it('geeft de eigen knop als de browser een prompt heeft, anders uitleg op iOS, anders niets', () => {
    expect(installatieAanbod({ standalone: false, ios: false, heeftPrompt: true })).toBe('prompt')
    expect(installatieAanbod({ standalone: false, ios: true, heeftPrompt: false })).toBe('ios')
    expect(installatieAanbod({ standalone: false, ios: false, heeftPrompt: false })).toBeNull()
  })
})

describe('platform en weergave', () => {
  it('herkent iPhone, iPad en een iPad die zich als Mac meldt, maar geen echte Mac', () => {
    expect(isIos({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)' })).toBe(true)
    expect(isIos({ userAgent: 'Mozilla/5.0 (Macintosh)', platform: 'MacIntel', maxTouchPoints: 5 })).toBe(true)
    expect(isIos({ userAgent: 'Mozilla/5.0 (Macintosh)', platform: 'MacIntel', maxTouchPoints: 0 })).toBe(false)
    expect(isIos({ userAgent: 'Mozilla/5.0 (Linux; Android 14)' })).toBe(false)
  })
  it('herkent de geïnstalleerde app aan display-mode of navigator.standalone (iOS)', () => {
    const win = standalone => ({ matchMedia: q => ({ matches: standalone && q === '(display-mode: standalone)' }) })
    expect(isStandalone(win(true), {})).toBe(true)
    expect(isStandalone(win(false), { standalone: true })).toBe(true)
    expect(isStandalone(win(false), {})).toBe(false)
  })
})

describe('de bewaarde prompt', () => {
  const maakWin = () => {
    const luisteraars = {}
    return { luisteraars, addEventListener: (type, f) => { luisteraars[type] = f } }
  }
  const maakEvent = outcome => ({ preventDefault: vi.fn(), prompt: vi.fn().mockResolvedValue(), userChoice: Promise.resolve({ outcome }) })

  it('houdt de dialoog van de browser vast tot de gebruiker erom vraagt, en gebruikt hem één keer', async () => {
    const win = maakWin()
    startInstallatieAanbod(win)
    const event = maakEvent('accepted')
    win.luisteraars.beforeinstallprompt(event)
    expect(event.preventDefault).toHaveBeenCalled()
    expect(event.prompt).not.toHaveBeenCalled()
    expect(await vraagInstallatie()).toBe('accepted')
    expect(event.prompt).toHaveBeenCalledTimes(1)
    expect(await vraagInstallatie()).toBeNull()
  })

  it('vergeet de prompt na appinstalled', async () => {
    const win = maakWin()
    startInstallatieAanbod(win)
    win.luisteraars.beforeinstallprompt(maakEvent('accepted'))
    win.luisteraars.appinstalled()
    expect(await vraagInstallatie()).toBeNull()
  })
})

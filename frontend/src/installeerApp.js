// Het aanbod om de app op het startscherm te zetten (#671). Chromium (Android, desktop) geeft een
// `beforeinstallprompt` die we bewaren tot de gebruiker erom vraagt; iOS Safari heeft geen prompt-API, daar leggen we
// de stappen uit. Draait de app al als geïnstalleerde app, dan valt er niets aan te bieden.
import { useSyncExternalStore } from 'react'

let uitgesteldePrompt = null
const luisteraars = new Set()
const meld = () => luisteraars.forEach(f => f())

// Vroeg aanroepen (main.jsx): de browser vuurt het event één keer, vaak vóór de eerste render van de menu's.
export function startInstallatieAanbod(win = window) {
  win.addEventListener('beforeinstallprompt', e => {
    e.preventDefault()
    uitgesteldePrompt = e
    meld()
  })
  win.addEventListener('appinstalled', () => {
    uitgesteldePrompt = null
    meld()
  })
}

export const isStandalone = (win, nav) => !!win.matchMedia?.('(display-mode: standalone)').matches || nav.standalone === true

// iPadOS meldt zich als Mac; de aanraakpunten onderscheiden hem van een echte Mac.
export const isIos = nav => /iPad|iPhone|iPod/.test(nav.userAgent || '') || (nav.platform === 'MacIntel' && nav.maxTouchPoints > 1)

// 'prompt': een eigen knop die de browserdialoog opent. 'ios': uitleg met stappen. null: niets aanbieden.
export function installatieAanbod({ standalone, ios, heeftPrompt }) {
  if (standalone) return null
  if (heeftPrompt) return 'prompt'
  return ios ? 'ios' : null
}

// De prompt is eenmalig: na gebruik geeft Chromium later een nieuw event, dus de bewaarde gaat weg.
export async function vraagInstallatie() {
  const prompt = uitgesteldePrompt
  if (!prompt) return null
  uitgesteldePrompt = null
  meld()
  await prompt.prompt()
  return (await prompt.userChoice).outcome
}

const abonneer = f => { luisteraars.add(f); return () => luisteraars.delete(f) }
const heeftPrompt = () => uitgesteldePrompt !== null

export function useInstallatieAanbod() {
  const prompt = useSyncExternalStore(abonneer, heeftPrompt, () => false)
  return installatieAanbod({ standalone: isStandalone(window, navigator), ios: isIos(navigator), heeftPrompt: prompt })
}

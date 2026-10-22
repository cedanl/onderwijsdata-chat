// Service worker van openEDUdata+ (#670). Alleen om de app installeerbaar te houden en offline te openen met
// de eigen verbindingsbanner; antwoorden en rapporten komen nooit uit een cache.
//
// - De app-shell (index.html) gaat network-first: een deploy komt direct door. Zonder verbinding krijgt een
//   navigatie de laatst geziene shell.
// - Bestanden onder /assets dragen een hash in hun naam en gaan cache-first. Grote bestanden (Plotly, maplibre,
//   ± 4,8 MB) blijven buiten de cache: offline is er toch geen grafiek om te tonen, en de opslag blijft klein.
// - Alles onder /api (gesprekken, rapporten, export van persoonsgegevens) gaat altijd rechtstreeks naar het netwerk.
// - Geen skipWaiting en geen clients.claim: een antwoord duurt minuten, dus een nieuwe worker mag geen open tab
//   overnemen. De worker wijzigt bovendien niet per deploy; de shell en de assets verversen zichzelf hierboven.
const CACHE_VOORVOEGSEL = 'edudata-'
const SHELL = `${CACHE_VOORVOEGSEL}shell-v1`
const ASSETS = `${CACHE_VOORVOEGSEL}assets-v1`
const SHELL_SLEUTEL = '/__shell'
const MAX_ASSET_BYTES = 1024 * 1024
const MAX_ASSETS = 80

const isApiPad = pad => pad === '/api' || pad.startsWith('/api/')
const isShellHtml = response => response.ok && (response.headers.get('content-type') || '').includes('text/html')

const bewaarShell = async response => (await caches.open(SHELL)).put(SHELL_SLEUTEL, response)

async function bewaarAsset(request, response) {
  // Gemeten op de gedecodeerde inhoud: content-length is bij gzip de gecomprimeerde grootte, of ontbreekt.
  if ((await response.clone().arrayBuffer()).byteLength > MAX_ASSET_BYTES) return
  const cache = await caches.open(ASSETS)
  await cache.put(request, response)
  // De oudste eerst weg (de cache bewaart de volgorde van toevoegen): hashnamen van oude deploys lopen anders op.
  const sleutels = await cache.keys()
  await Promise.all(sleutels.slice(0, Math.max(0, sleutels.length - MAX_ASSETS)).map(s => cache.delete(s)))
}

// Eerste installatie: de shell en de bestanden die hij noemt, want de pagina die dit registreert is zonder
// worker geladen en zou anders niet offline kunnen starten. Mislukt het, dan installeert de worker niet.
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const response = await fetch('/', { cache: 'reload' })
    if (!isShellHtml(response)) throw new Error('shell niet opgehaald')
    const html = await response.clone().text()
    await bewaarShell(response)
    const bestanden = [...new Set(html.match(/\/assets\/[^"'\s)]+/g) || [])]
    await (await caches.open(ASSETS)).addAll(bestanden)
  })())
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(namen => Promise.all(
      namen.filter(n => n.startsWith(CACHE_VOORVOEGSEL) && n !== SHELL && n !== ASSETS).map(n => caches.delete(n))
    ))
  )
})

async function navigatie(event) {
  try {
    const response = await fetch(event.request)
    if (isShellHtml(response)) event.waitUntil(bewaarShell(response.clone()))
    return response
  } catch {
    return (await caches.match(SHELL_SLEUTEL, { cacheName: SHELL })) || Response.error()
  }
}

async function asset(event) {
  const bewaard = await caches.match(event.request, { cacheName: ASSETS })
  if (bewaard) return bewaard
  const response = await fetch(event.request)
  if (response.status === 200) event.waitUntil(bewaarAsset(event.request, response.clone()))
  return response
}

self.addEventListener('fetch', event => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin || isApiPad(url.pathname)) return
  if (request.mode === 'navigate') event.respondWith(navigatie(event))
  else if (url.pathname.startsWith('/assets/')) event.respondWith(asset(event))
})

// De service worker (public/sw.js, #670), uitgevoerd tegen een in-memory Cache API en een nep-netwerk.
import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'

const BRON = readFileSync(new URL('../../public/sw.js', import.meta.url), 'utf8')
const ORIGIN = 'https://edu.test'
const INDEX = '<html><script src="/assets/index-a1.js"></script><link href="/assets/index-b2.css"></head>'

const sleutel = r => (typeof r === 'string' ? new URL(r, ORIGIN).href : r.url)

function maakCaches(haal) {
  const winkels = new Map()
  const open = async naam => {
    if (!winkels.has(naam)) winkels.set(naam, new Map())
    const winkel = winkels.get(naam)
    return {
      put: async (r, resp) => { winkel.set(sleutel(r), resp) },
      keys: async () => [...winkel.keys()].map(url => ({ url })),
      delete: async r => winkel.delete(sleutel(r)),
      addAll: async urls => { for (const u of urls) winkel.set(sleutel(u), await haal(u)) },
    }
  }
  const match = async (r, { cacheName } = {}) => {
    for (const [naam, winkel] of winkels) {
      const gevonden = (!cacheName || naam === cacheName) && winkel.get(sleutel(r))
      if (gevonden) return gevonden.clone()
    }
    return undefined
  }
  return { open, match, keys: async () => [...winkels.keys()], delete: async n => winkels.delete(n) }
}

const html = (tekst = INDEX) => new Response(tekst, { headers: { 'content-type': 'text/html; charset=utf-8' } })

function laadWorker(netwerk) {
  const luisteraars = {}
  const nepFetch = vi.fn(async r => netwerk(sleutel(r)))
  const caches = maakCaches(nepFetch)
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type, fn) => { luisteraars[type] = fn },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
  }
  new Function('self', 'caches', 'fetch', BRON)(self, caches, nepFetch)

  const gebeurtenis = async (type, extra = {}) => {
    const wachtend = []
    let antwoord
    luisteraars[type]({ ...extra, waitUntil: p => wachtend.push(p), respondWith: p => { antwoord = p } })
    // Eerst het antwoord: waitUntil-werk (het bewaren in de cache) start pas als de worker het antwoord opbouwt.
    if (antwoord !== undefined) await antwoord
    await Promise.all(wachtend)
    return antwoord
  }
  return {
    self, caches, nepFetch,
    installeer: () => gebeurtenis('install'),
    activeer: () => gebeurtenis('activate'),
    vraag: async request => {
      const antwoord = await gebeurtenis('fetch', { request })
      return antwoord === undefined ? { onderschept: false } : { onderschept: true, resp: await antwoord }
    },
  }
}

const GET = (pad, mode = 'cors') => ({ method: 'GET', url: ORIGIN + pad, mode })
const online = (extra = {}) => url => {
  const pad = new URL(url).pathname
  if (pad in extra) return extra[pad]()
  return pad === '/' || pad === '/chat' ? html() : new Response('body', { status: 200 })
}

describe('install en activate', () => {
  it('bewaart de shell en de bestanden die hij noemt, zodat de eerste pagina offline kan starten', async () => {
    const w = laadWorker(online())
    await w.installeer()
    expect(await w.caches.keys()).toEqual(['edudata-shell-v1', 'edudata-assets-v1'])
    expect(await w.caches.match('/__shell')).toBeDefined()
    expect(await w.caches.match('/assets/index-a1.js')).toBeDefined()
    expect(await w.caches.match('/assets/index-b2.css')).toBeDefined()
  })

  it('installeert niet als de shell geen html is, in plaats van een kapotte worker te registreren', async () => {
    const w = laadWorker(() => new Response('{"detail":"nee"}', { status: 404 }))
    await expect(w.installeer()).rejects.toThrow('shell niet opgehaald')
  })

  it('neemt een open tab niet over: geen skipWaiting en geen clients.claim', async () => {
    const w = laadWorker(online())
    await w.installeer()
    await w.activeer()
    expect(w.self.skipWaiting).not.toHaveBeenCalled()
    expect(w.self.clients.claim).not.toHaveBeenCalled()
  })

  it('ruimt oude edudata-caches op en laat andere caches met rust', async () => {
    const w = laadWorker(online())
    await w.installeer()
    await (await w.caches.open('edudata-shell-v0')).put('/x', html())
    await (await w.caches.open('iets-anders')).put('/y', html())
    await w.activeer()
    expect(await w.caches.keys()).toEqual(['edudata-shell-v1', 'edudata-assets-v1', 'iets-anders'])
  })
})

describe('wat nooit onderschept wordt', () => {
  it('laat /api, schrijvende methoden en andere origins rechtstreeks naar het netwerk', async () => {
    const w = laadWorker(online())
    const verzoeken = [
      GET('/api/conversations'),
      GET('/api'),
      GET('/api/mijn-gegevens/export', 'navigate'),
      { method: 'POST', url: ORIGIN + '/assets/x.js', mode: 'cors' },
      { method: 'GET', url: 'https://elders.test/assets/x.js', mode: 'cors' },
    ]
    for (const r of verzoeken) expect((await w.vraag(r)).onderschept, r.url).toBe(false)
    expect(await w.caches.keys()).toEqual([])
  })

  it('bewaart nooit een antwoord van /api, ook niet na een geslaagde navigatie', async () => {
    const w = laadWorker(online())
    await w.vraag(GET('/api/workbooks'))
    await w.vraag(GET('/chat', 'navigate'))
    for (const naam of await w.caches.keys()) {
      const sleutels = await (await w.caches.open(naam)).keys()
      expect(sleutels.filter(s => new URL(s.url).pathname.startsWith('/api')), naam).toEqual([])
    }
  })
})

describe('navigaties', () => {
  it('geeft online het verse antwoord en bewaart die shell', async () => {
    const w = laadWorker(online({ '/chat': () => html('<html>nieuw</html>') }))
    const { resp } = await w.vraag(GET('/chat', 'navigate'))
    expect(await resp.text()).toBe('<html>nieuw</html>')
    expect(await (await w.caches.match('/__shell')).text()).toBe('<html>nieuw</html>')
  })

  it('geeft offline de laatst geziene shell, ook op een pad dat nooit is bezocht', async () => {
    let verbonden = true
    const w = laadWorker(() => {
      if (!verbonden) throw new TypeError('Failed to fetch')
      return html('<html>shell</html>')
    })
    await w.vraag(GET('/chat', 'navigate'))
    verbonden = false
    const { resp } = await w.vraag(GET('/rapporten', 'navigate'))
    expect(await resp.text()).toBe('<html>shell</html>')
  })

  it('geeft offline zonder shell een netwerkfout, geen verzonnen pagina', async () => {
    const w = laadWorker(() => { throw new TypeError('Failed to fetch') })
    const { resp } = await w.vraag(GET('/chat', 'navigate'))
    expect(resp.type).toBe('error')
  })

  it('bewaart een foutpagina niet als shell', async () => {
    const w = laadWorker(() => new Response('{"detail":"fout"}', { status: 500, headers: { 'content-type': 'text/html' } }))
    await w.vraag(GET('/chat', 'navigate'))
    expect(await w.caches.keys()).toEqual([])
  })
})

describe('assets', () => {
  it('haalt een bestand één keer op en geeft het daarna uit de cache', async () => {
    const w = laadWorker(online())
    await w.vraag(GET('/assets/ChatPage-x1.js'))
    const { resp } = await w.vraag(GET('/assets/ChatPage-x1.js'))
    expect(await resp.text()).toBe('body')
    expect(w.nepFetch).toHaveBeenCalledTimes(1)
  })

  it('bewaart een groot bestand (Plotly) en een mislukt antwoord niet', async () => {
    const w = laadWorker(online({
      '/assets/plotly-x.js': () => new Response('x'.repeat(1024 * 1024 + 1)),
      '/assets/weg.js': () => new Response('nee', { status: 404 }),
    }))
    expect((await w.vraag(GET('/assets/plotly-x.js'))).resp.status).toBe(200)
    expect((await w.vraag(GET('/assets/weg.js'))).resp.status).toBe(404)
    expect(await w.caches.match('/assets/plotly-x.js')).toBeUndefined()
    expect(await w.caches.match('/assets/weg.js')).toBeUndefined()
  })

  it('houdt hoogstens 80 bestanden en gooit de oudste weg', async () => {
    const w = laadWorker(online())
    for (let i = 0; i < 85; i++) await w.vraag(GET(`/assets/chunk-${i}.js`))
    const sleutels = await (await w.caches.open('edudata-assets-v1')).keys()
    expect(sleutels).toHaveLength(80)
    expect(await w.caches.match('/assets/chunk-0.js')).toBeUndefined()
    expect(await w.caches.match('/assets/chunk-84.js')).toBeDefined()
  })
})

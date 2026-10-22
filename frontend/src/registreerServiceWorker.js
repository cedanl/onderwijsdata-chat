// De service worker (frontend/public/sw.js, #670) wordt pas na `load` geregistreerd, zodat hij het eerste laden
// niet vertraagt, en alleen in een build: `vite dev` serveert hem niet en een worker in dev verstopt wijzigingen.
// Een mislukte registratie mag de app niet raken: zonder worker werkt alles, alleen offline starten niet.
export function registreerServiceWorker({
  nav = typeof navigator === 'undefined' ? {} : navigator,
  win = typeof window === 'undefined' ? null : window,
  productie = import.meta.env.PROD,
} = {}) {
  if (!productie || !win || !('serviceWorker' in nav)) return
  const registreer = () => { nav.serviceWorker.register('/sw.js').catch(() => {}) }
  if (win.document.readyState === 'complete') registreer()
  else win.addEventListener('load', registreer, { once: true })
}

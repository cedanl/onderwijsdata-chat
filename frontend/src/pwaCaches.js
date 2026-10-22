// De caches van de service worker (public/sw.js, #670) bevatten alleen de shell en bestanden onder /assets, nooit
// gegevens van een account. Toch gaan ze weg als de sessie eindigt (uitloggen, verlopen, "Verwijder al mijn gegevens"):
// een gedeeld apparaat houdt dan niets van de app achter, en wat er blijft is aantoonbaar leeg. De pagina wist ze zelf;
// dat hoeft niet via de worker en is af te wachten. Een volgende pagina vult ze weer via de worker.
// Hetzelfde voorvoegsel als CACHE_VOORVOEGSEL in sw.js (een test bewaakt dat).
export const PWA_CACHE_VOORVOEGSEL = 'edudata-'

export async function wisPwaCaches(cacheStore = globalThis.caches ?? null) {
  if (!cacheStore) return
  try {
    const namen = await cacheStore.keys()
    await Promise.all(namen.filter(n => n.startsWith(PWA_CACHE_VOORVOEGSEL)).map(n => cacheStore.delete(n)))
  } catch {
    // Een geblokkeerde Cache API (privévenster) laat niets achter om te wissen.
  }
}

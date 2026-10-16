// De themakeuze van de app in het rapport (#568). Het rapport staat in een sandbox-frame met een opaque origin:
// de app komt niet bij zijn document, dus de keuze reist mee in de srcDoc als klasse op <html>, dezelfde klassen
// als theme.js op de app zet. Een rapport van deze build heeft regels voor die klassen (reportHtml.js); een ouder
// rapport kent ze niet en blijft de OS-voorkeur volgen. Modus 'system' zet niets: dan beslist prefers-color-scheme,
// in het frame dezelfde als in de app. De download krijgt geen klasse: los van de app telt alleen de OS-voorkeur.
const HTML_TAG = /<html(\s[^>]*)?>/i
const CLASS_ATTR = /\bclass\s*=\s*(["'])([^"']*)\1/i

export const THEMA_KLASSEN = ['light', 'dark']

export function metThema(html, mode) {
  if (!html || !THEMA_KLASSEN.includes(mode)) return html
  return String(html).replace(HTML_TAG, (tag, attrs = '') => (
    CLASS_ATTR.test(attrs)
      ? tag.replace(CLASS_ATTR, (m, q, v) => `class=${q}${v.split(/\s+/).filter(k => k && !THEMA_KLASSEN.includes(k)).concat(mode).join(' ')}${q}`)
      : `${tag.slice(0, -1)} class="${mode}">`
  ))
}

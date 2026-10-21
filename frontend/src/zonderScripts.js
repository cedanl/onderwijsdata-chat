// A report without its <script> blocks, for a thumbnail (#654). The thumbnail frame has sandbox="" and blocks every
// script anyway; each blocked one only put a "Blocked script execution" line in the console and weighed on the DOM.
// Noise reduction, not a security boundary: sandbox="" stays the boundary.
// A block runs from <script ...> to the first </script ...>, as in HTML; one without an end tag runs to the end.
// The tag name must end there, so an element like <script-kaart> stays.
const SCRIPT_BLOK = /<script(?=[\s/>])[\s\S]*?(?:<\/script(?=[\s/>])[^>]*>|$)/gi

export function zonderScripts(html) {
  if (!html) return html
  return String(html).replace(SCRIPT_BLOK, '')
}

// Het Telling-blok dat de backend onder een antwoord zet (agent/telling.py). De DUO-tekst is
// soms 600 tekens; onder een korte vraag tonen we de eerste zin en klappen de rest uit (#402).
const KOP = '\n\n**Telling**\n'
const EERSTE_ZIN = /^(.*?[.!?])(\s|$)/

export function splitsTelling(content) {
  const i = (content || '').lastIndexOf(KOP)
  if (i < 0) return { antwoord: content, telling: null, samenvatting: null }
  const telling = content.slice(i + KOP.length).trim()
  const eerste = telling.split('\n')[0].replace(/^-\s*/, '')
  const definitie = eerste.slice(eerste.indexOf(': ') + 2)
  const zin = definitie.match(EERSTE_ZIN)?.[1] ?? definitie
  return { antwoord: content.slice(0, i), telling, samenvatting: zin }
}

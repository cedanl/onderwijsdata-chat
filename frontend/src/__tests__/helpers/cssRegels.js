// Gedeeld door de CSS-tests (tapTargets, inputFontSize, composerStabiel; #842); zelf geen testbestand.

// Regels op topniveau en in @media-blokken, in bestandsvolgorde: { media, selectors, body, index }. `media` is de
// prelude van het omringende @media-blok (of `media` voor regels op topniveau), `index` de positie in de lijst.
// Andere at-rules (@keyframes, @font-face, @supports) slaat hij over.
export function parseRules(text, media = null) {
  const rules = []
  verzamel(text, media, rules)
  return rules
}

function verzamel(text, media, rules) {
  let i = 0
  while (i < text.length) {
    const open = text.indexOf('{', i)
    if (open === -1) break
    const prelude = text.slice(i, open).trim()
    let depth = 1
    let j = open + 1
    while (depth > 0 && j < text.length) {
      if (text[j] === '{') depth++
      else if (text[j] === '}') depth--
      j++
    }
    const inner = text.slice(open + 1, j - 1)
    if (prelude.startsWith('@media')) verzamel(inner, prelude, rules)
    else if (!prelude.startsWith('@')) {
      rules.push({ media, selectors: prelude.split(',').map(s => s.trim()), body: inner, index: rules.length })
    }
    i = j
  }
}

// De tekst van een bewaard rapport, gelezen uit zijn HTML (#746). Een rapport wordt alleen als HTML bewaard
// (reportHtml.js, ChatPage); de spec is na het bewaren weg. DOMParser bouwt een inert document: geen script loopt,
// en er komt alleen tekst uit, plus een link die een http(s)-adres is (bronLink.js). Zo werkt het ook voor een
// rapport van vóór deze build. Een onderdeel dat een ouder rapport niet heeft, blijft leeg.
// De server heeft een Python-tweeling voor "Download als Word" (tools/rapport_docx/uit_html.py, #1038): een wijziging
// hier hoort daar ook; tests/fixtures/rapport_docx houdt beide gelijk (rapportDocxPariteit.test.js).
import { veiligeBronUrl } from './bronLink'

const tekst = el => (el?.textContent || '').replace(/\s+/g, ' ').trim()
const alle = (root, selector) => [...root.querySelectorAll(selector)]
const teksten = (root, selector) => alle(root, selector).map(tekst).filter(Boolean)

// Een rapport uit buildReportHtml heeft altijd het blok met de onderzoeksvraag; andere HTML krijgt geen knop.
export function kanMarkdown(html) {
  return typeof html === 'string' && html.includes('class="vraag"')
}

// Eén definitie: het begrip en de delen, zoals reportHtml.js ze toont (één zin, of een opsomming, #748).
function definitie(el) {
  const lijst = teksten(el, '.def-lijst li')
  const delen = lijst.length ? lijst : [tekst(el.querySelector('.def-desc'))].filter(Boolean)
  return { begrip: tekst(el.querySelector('.def-term')), delen }
}

// De bronregel onder een grafiek (#569): de regel zonder de link, en de link apart.
function bronregel(el) {
  if (!el) return { regel: '', url: null, linkTekst: '' }
  const kopie = el.cloneNode(true)
  const link = kopie.querySelector('a')
  link?.remove()
  return {
    regel: tekst(kopie).replace(/\s*·$/, ''),
    url: veiligeBronUrl(link?.getAttribute('href')),
    linkTekst: tekst(link),
  }
}

function visualisatie(el) {
  return {
    titel: tekst(el.querySelector('.vis-title')),
    noot: tekst(el.querySelector('.vis-noot')),
    bron: bronregel(el.querySelector('.vis-bron')),
    toelichting: tekst(el.querySelector('.vis-note')),
  }
}

// De conclusie terug naar Markdown: reportHtml.js maakte van koppen h3, van **vet** <strong>, van een opsomming
// <ul>/<ol> met <li> (een ouder rapport: <li> zonder lijst), van een pipetabel een <table> (#1075; een ouder rapport:
// tekstregels) en van regels <br>/<p>. Alleen die vormen komen terug; de rest is tekst.
const isElement = (kind, tag) => kind.nodeType === window.Node.ELEMENT_NODE && kind.tagName === tag

// Een cel als één regel tekst: een | erin zou de tabel breken.
const celMarkdown = cel => proseMarkdown(cel).replace(/\s+/g, ' ').trim().replace(/\|/g, '/')

function uitlijning(cel) {
  const waarde = (cel.getAttribute('style') || '').match(/text-align:\s*(left|right|center)/)?.[1]
  return { left: ':---', right: '---:', center: ':---:' }[waarde] || '---'
}

function tabelMarkdown(tabel) {
  const rijen = alle(tabel, 'tr').filter(tr => tr.closest('table') === tabel)
  if (!rijen.length) return ''
  const cellen = tr => [...tr.children].filter(c => c.tagName === 'TH' || c.tagName === 'TD')
  const regel = delen => `| ${delen.join(' | ')} |`
  const [kop, ...rest] = rijen
  return [
    regel(cellen(kop).map(celMarkdown)),
    `|${cellen(kop).map(uitlijning).join('|')}|`,
    ...rest.map(tr => regel(cellen(tr).map(celMarkdown))),
  ].join('\n')
}

function proseMarkdown(node) {
  let uit = ''
  for (const kind of node.childNodes) {
    if (kind.nodeType === window.Node.TEXT_NODE) uit += kind.textContent.replace(/\s+/g, ' ')
    if (kind.nodeType !== window.Node.ELEMENT_NODE) continue
    if (kind.tagName === 'TABLE') { uit += `\n\n${tabelMarkdown(kind)}\n\n`; continue }
    if (kind.tagName === 'OL') {
      const items = [...kind.children].filter(li => isElement(li, 'LI'))
      uit += `\n\n${items.map((li, i) => `${i + 1}. ${proseMarkdown(li).trim()}`).join('\n')}\n\n`
      continue
    }
    const binnen = proseMarkdown(kind)
    if (kind.tagName === 'BR') uit += '\n'
    else if (kind.tagName === 'STRONG' || kind.tagName === 'B') uit += `**${binnen.trim()}**`
    else if (/^H[1-6]$/.test(kind.tagName)) uit += `\n\n### ${binnen.trim()}\n\n`
    else if (kind.tagName === 'LI') uit += `\n- ${binnen.trim()}\n`
    else if (['P', 'DIV', 'UL'].includes(kind.tagName)) uit += `\n\n${binnen}\n\n`
    else uit += binnen
  }
  return uit
}

// Regels zonder randspaties, hooguit één lege regel achter elkaar, en geen lege regel binnen een opsomming.
function netjes(markdown) {
  const regels = markdown.split('\n').map(r => r.trim()).filter((r, i, alle) => r || alle[i - 1])
  const inOpsomming = i => regels[i - 1]?.startsWith('- ') && regels[i + 1]?.startsWith('- ')
  return regels.filter((r, i) => r || !inOpsomming(i)).join('\n').trim()
}

export function rapportUitHtml(html) {
  const doc = new window.DOMParser().parseFromString(String(html || ''), 'text/html')
  const prose = doc.querySelector('.conf .prose')
  return {
    title: tekst(doc.querySelector('.header h1')),
    meta: teksten(doc, '.meta-chip'),
    instelling: tekst(doc.querySelector('.instelling-badge')),
    afwijkingen: teksten(doc, '.afwijking li'),
    onderzoeksvraag: tekst(doc.querySelector('.vraag-text')),
    beantwoordt: teksten(doc, '.scope-yes + ul li'),
    beantwoordtNiet: teksten(doc, '.scope-no + ul li'),
    definities: alle(doc, '.def').map(definitie),
    visualisaties: alle(doc, '.vis').map(visualisatie),
    conclusie: prose ? netjes(proseMarkdown(prose)) : '',
    bronnen: teksten(doc, '.bronnen li'),
    herkomst: teksten(doc, '.manifest > div'),
  }
}

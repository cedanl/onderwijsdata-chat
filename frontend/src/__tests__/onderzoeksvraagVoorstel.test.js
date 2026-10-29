// #751: het veld bij "Genereer rapport" staat al ingevuld met de onderzoeksvraag zoals die in het gesprek groeide
// (#732): de regel "Onderzoeksvraag:" uit het laatste antwoord dat er een heeft, anders de eerste vraag.
import { describe, it, expect } from 'vitest'
import { onderzoeksvraagVoorstel } from '../onderzoeksvraagVoorstel'

const EERSTE = 'Hoe is de trend van instroom in B Computing Science, B Informatica en B Computer Science?'
const BREED = 'Hoe ontwikkelt de instroom in drie informatica-bachelors zich?'
const WO = 'Hoe ontwikkelt de instroom in de wo-bachelors B Computing Science, B Informatica en B Computer Science zich?'

const vraag = content => ({ role: 'user', content })
const antwoord = (content, extra = {}) => ({ role: 'assistant', content, done: true, ...extra })

describe('onderzoeksvraagVoorstel (#751)', () => {
  it('neemt de regel uit het laatste antwoord dat er een heeft', () => {
    const berichten = [
      vraag(EERSTE),
      antwoord(`**Onderzoeksvraag:** ${BREED}\n\nDe instroom daalt.`),
      vraag("Ik wil het alleen zien voor universitaire bachelor's."),
      antwoord(`**Onderzoeksvraag:** ${WO}\n\nOok in het wo daalt de instroom.`),
      vraag('Kun je de kleuren aanpassen?'),
      antwoord('Dat doe ik, zie de grafiek.'),
    ]
    expect(onderzoeksvraagVoorstel(berichten)).toBe(WO)
  })

  it.each([
    ['dubbele punt binnen het vet', `**Onderzoeksvraag:** ${WO}`],
    ['dubbele punt buiten het vet', `**Onderzoeksvraag**: ${WO}`],
    ['zonder vet', `Onderzoeksvraag: ${WO}`],
    ['in een citaat', `> **Onderzoeksvraag:** ${WO}`],
    ['met de vraag cursief', `**Onderzoeksvraag:** *${WO}*`],
    ['na de kern van een lang antwoord', `De instroom daalt sinds 2021.\n\n**Onderzoeksvraag:** ${WO}\n\nToelichting.`],
  ])('%s', (_naam, content) => {
    expect(onderzoeksvraagVoorstel([vraag(EERSTE), antwoord(content)])).toBe(WO)
  })

  it('binnen één antwoord wint de laatste regel', () => {
    const content = `**Onderzoeksvraag:** ${BREED}\n\nNa de afbakening:\n\n**Onderzoeksvraag:** ${WO}`
    expect(onderzoeksvraagVoorstel([vraag(EERSTE), antwoord(content)])).toBe(WO)
  })

  it('zonder regel de eerste vraag van de gebruiker, op één regel', () => {
    const berichten = [
      antwoord('Welkom'),
      vraag(`  ${EERSTE.replace(' in ', '\n in ')}  `),
      antwoord('De instroom daalt.'),
      vraag('En in het wo?'),
    ]
    expect(onderzoeksvraagVoorstel(berichten)).toBe(EERSTE)
  })

  it.each([
    ['gestopt', { stopped: true }],
    ['afgebroken door de verbinding', { interrupted: true }],
    ['afgebroken in een heropend gesprek', { afgebroken: true }],
    ['een foutmelding', { isError: true }],
  ])('een antwoord dat %s is telt niet', (_naam, vlag) => {
    const berichten = [
      vraag(EERSTE),
      antwoord(`**Onderzoeksvraag:** ${BREED}`),
      vraag('Alleen het wo.'),
      antwoord('**Onderzoeksvraag:** Hoe ontwikkelt de instroom in de wo-', vlag),
    ]
    expect(onderzoeksvraagVoorstel(berichten)).toBe(BREED)
  })

  it('een vermelding midden in een zin is geen regel', () => {
    const berichten = [vraag(EERSTE), antwoord('De onderzoeksvraag: die stel je straks bij het rapport.')]
    expect(onderzoeksvraagVoorstel(berichten)).toBe(EERSTE)
  })

  it('een lege regel telt niet', () => {
    const berichten = [vraag(EERSTE), antwoord(`**Onderzoeksvraag:** ${BREED}`), antwoord('**Onderzoeksvraag:**  ')]
    expect(onderzoeksvraagVoorstel(berichten)).toBe(BREED)
  })

  it('zonder vraag en zonder regel: leeg', () => {
    expect(onderzoeksvraagVoorstel([])).toBe('')
    expect(onderzoeksvraagVoorstel([antwoord('Welkom'), { role: 'assistant', figures: [{}] }])).toBe('')
  })
})

import { describe, it, expect } from 'vitest'
import { scheidNoot, scheidNootJson } from '../figuurNoot'

// #651: de afrondingsnoot van CBS stond als ondertitel van 11 px in de figuur. Hij staat nu als tekstregel onder de
// grafiek; dit haalt hem uit de figuur, ook uit een figuur van vóór die wijziging.
const NOOT = 'De aantallen zijn door CBS afgerond op 10-tallen: een som, verschil of percentage daarvan is niet exact.'
const titel = { text: 'Ingeschrevenen HO', font: { size: 16, color: '#222' } }
const nieuw = { data: [{ type: 'bar', x: ['2024'], y: [1] }], layout: { title: titel, margin: { t: 60 }, meta: { data: [], afrondingsnoot: NOOT } } }
const oud = {
  data: [{ type: 'bar', x: ['2024'], y: [1] }],
  layout: {
    title: { ...titel, yref: 'container', yanchor: 'top', y: 0.98, subtitle: { text: 'De aantallen zijn door CBS afgerond op 10-tallen: een<br>som, verschil of percentage <b>daarvan</b> is niet exact.', font: { size: 11, color: '#666' } } },
    margin: { t: 100 },
    meta: { data: [] },
  },
}

describe('scheidNoot', () => {
  it('leest de noot uit layout.meta.afrondingsnoot en laat de figuur zonder ondertitel ongewijzigd', () => {
    const { figure, noot } = scheidNoot(nieuw)
    expect(noot).toBe(NOOT)
    expect(figure).toBe(nieuw)
  })

  it('haalt de ondertitel uit een figuur van vóór #651 en geeft hem als platte tekst', () => {
    const kopie = structuredClone(oud)
    const { figure, noot } = scheidNoot(oud)
    expect(noot).toBe(NOOT)
    expect(figure.layout.title).not.toHaveProperty('subtitle')
    expect(figure.layout.title).toMatchObject({ text: titel.text, font: titel.font })
    expect(figure.layout.meta).toEqual(oud.layout.meta)
    expect(figure.data).toBe(oud.data)
    expect(oud).toEqual(kopie)
  })

  it('geeft het eigen veld voorrang en haalt een ondertitel er toch uit', () => {
    const beide = { ...oud, layout: { ...oud.layout, meta: { afrondingsnoot: NOOT } } }
    const { figure, noot } = scheidNoot(beide)
    expect(noot).toBe(NOOT)
    expect(figure.layout.title).not.toHaveProperty('subtitle')
  })

  it('laat een figuur zonder noot, zonder layout of zonder figuur ongewijzigd, met een lege noot', () => {
    const zonder = { data: [], layout: { title: titel, meta: { data: [] } } }
    for (const invoer of [zonder, { data: [] }, { layout: { title: 'Kort' } }, null, undefined]) {
      const { figure, noot } = scheidNoot(invoer)
      expect(figure).toBe(invoer)
      expect(noot).toBe('')
    }
    const leeg = { data: [], layout: { title: { ...titel, subtitle: { text: '  ' } }, meta: { afrondingsnoot: '' } } }
    expect(scheidNoot(leeg)).toEqual({ figure: leeg, noot: '' })
  })
})

describe('scheidNootJson', () => {
  it('geeft het figuurJSON zonder ondertitel en de noot', () => {
    const { figureJson, noot } = scheidNootJson(JSON.stringify(oud))
    expect(noot).toBe(NOOT)
    expect(figureJson).not.toContain('subtitle')
    expect(JSON.parse(figureJson).layout.title.text).toBe(titel.text)
  })

  it('laat een figuur met het eigen veld als hetzelfde JSON staan', () => {
    const json = JSON.stringify(nieuw)
    expect(scheidNootJson(json)).toEqual({ figureJson: json, noot: NOOT })
  })

  it('laat onleesbaar JSON en een figuur zonder noot ongewijzigd, met een lege noot', () => {
    for (const json of ['{niet json', '', 'null', JSON.stringify({ data: [], layout: { title: titel } }), undefined]) {
      expect(scheidNootJson(json)).toEqual({ figureJson: json, noot: '' })
    }
  })
})

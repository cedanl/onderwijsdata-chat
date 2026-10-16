import { describe, it, expect } from 'vitest'
import { titelRegels, tekensPerRegel, titelOpBreedte } from '../figureTitel'

const regels = tekst => tekst.split('<br>')
const zonderTags = tekst => tekst.replace(/<[^>]*>/g, '')

// #587: op een telefoon viel het eind van de titel van de figuur ("…, 2020/").
const ISSUE = 'Mbo-studenten totaal (incl. extranei), 2020/2021 – 2024/2025'

describe('titelRegels', () => {
  it('geeft een korte titel ongewijzigd terug', () => {
    expect(titelRegels('Mbo-studenten per jaar', 30)).toBe('Mbo-studenten per jaar')
    expect(titelRegels('Twee  spaties blijven staan', 30)).toBe('Twee  spaties blijven staan')
  })

  it('breekt een lange titel op spaties, zonder regel langer dan de grens', () => {
    const uit = titelRegels(ISSUE, 30)
    expect(uit).toBe('Mbo-studenten totaal (incl.<br>extranei), 2020/2021 –<br>2024/2025')
    for (const regel of regels(uit)) expect(regel.length).toBeLessThanOrEqual(30)
    expect(uit.replaceAll('<br>', ' ')).toBe(ISSUE)
  })

  it('vult elke regel zo ver als het kan', () => {
    expect(titelRegels(ISSUE, 36)).toBe('Mbo-studenten totaal (incl.<br>extranei), 2020/2021 – 2024/2025')
  })

  it('laat een woord dat langer is dan de grens heel, op een eigen regel', () => {
    expect(titelRegels('Aantal arbeidsmarktrelevantiecategorieën per sector', 12))
      .toBe('Aantal<br>arbeidsmarktrelevantiecategorieën<br>per sector')
    expect(titelRegels('Arbeidsmarktrelevantie', 5)).toBe('Arbeidsmarktrelevantie')
  })

  it('laat een bestaande <br> staan en breekt elk deel op zichzelf', () => {
    expect(titelRegels('Studenten hoger onderwijs<br>naar sector en jaar', 15))
      .toBe('Studenten hoger<br>onderwijs<br>naar sector en<br>jaar')
    expect(titelRegels('Kort<br/>ook kort', 15)).toBe('Kort<br/>ook kort')
    expect(titelRegels('Een titel die breekt<BR>en verder', 12)).toBe('Een titel<br>die breekt<BR>en verder')
  })

  it('telt tekst in tags niet mee en splitst een tag nooit', () => {
    expect(titelRegels('<b>Studenten</b> hoger onderwijs', 26)).toBe('<b>Studenten</b> hoger onderwijs')
    const link = '<a href="https://example.org/a b" target="_blank">Bron</a> van de cijfers in deze grafiek'
    const uit = titelRegels(link, 20)
    expect(uit).toContain('<a href="https://example.org/a b" target="_blank">Bron</a>')
    for (const regel of regels(uit)) expect(zonderTags(regel).length).toBeLessThanOrEqual(20)
  })

  it('telt een entiteit als één teken', () => {
    expect(titelRegels('Studenten &amp; docenten', 20)).toBe('Studenten &amp; docenten')
  })

  it('geeft een lege of niet-tekst titel terug zoals hij was', () => {
    expect(titelRegels('', 10)).toBe('')
    expect(titelRegels(undefined, 10)).toBe(undefined)
    expect(titelRegels(null, 10)).toBe(null)
    const object = { text: ISSUE }
    expect(titelRegels(object, 10)).toBe(object)
  })

  it('laat de titel staan zonder bruikbare grens', () => {
    expect(titelRegels(ISSUE, 0)).toBe(ISSUE)
    expect(titelRegels(ISSUE, undefined)).toBe(ISSUE)
    expect(titelRegels(ISSUE, NaN)).toBe(ISSUE)
  })
})

describe('tekensPerRegel', () => {
  it('rekent pixels en lettergrootte om in hele tekens', () => {
    expect(tekensPerRegel(268, 16)).toBe(29)
    expect(tekensPerRegel(0, 16)).toBe(0)
  })

  it('past minder tekens van een grotere letter op een regel', () => {
    expect(tekensPerRegel(268, 20)).toBeLessThan(tekensPerRegel(268, 16))
  })
})

describe('titelOpBreedte', () => {
  const titel = { text: ISSUE, font: { size: 16, color: '#222' } }

  it('laat de titel staan zonder bekende breedte', () => {
    expect(titelOpBreedte(titel, 0, 32)).toEqual({ title: titel, extra: 0 })
    expect(titelOpBreedte(titel, undefined, 32).title).toBe(titel)
  })

  it('laat een titel die past precies zoals hij was, zonder extra marge', () => {
    expect(titelOpBreedte(titel, 1200, 32)).toEqual({ title: titel, extra: 0 })
    expect(titelOpBreedte('Kort', 268, 32)).toEqual({ title: 'Kort', extra: 0 })
  })

  it('breekt een te lange titel en rekent per extra regel de regelafstand van Plotly', () => {
    const { title, extra } = titelOpBreedte(titel, 268, 32)
    expect(regels(title.text).length).toBe(3)
    expect(extra).toBeCloseTo(2 * 16 * 1.3)
    expect(title.font).toEqual({ size: 16, color: '#222' })
  })

  it('gebruikt de lettergrootte van de titel, en 16 zonder', () => {
    const groot = titelOpBreedte({ ...titel, font: { size: 20 } }, 268, 32)
    expect(groot.extra).toBeCloseTo((regels(groot.title.text).length - 1) * 20 * 1.3)
    const kaal = titelOpBreedte(ISSUE, 268, 32)
    expect(kaal.extra).toBeCloseTo((regels(kaal.title.text).length - 1) * 16 * 1.3)
  })

  it('maakt van een titel als tekst een titelobject met de afgebroken tekst', () => {
    const { title } = titelOpBreedte(ISSUE, 268, 32)
    expect(title.text).toBe(titelRegels(ISSUE, tekensPerRegel(268, 16)))
  })

  // Plotly zet een titel zonder plaats met de basislijn midden in de bovenmarge (16 bij 32); bij meer
  // regels komt de basislijn van de eerste regel op y + pad.t, want de kaphoogte (dy) vervalt dan.
  it('zet een afgebroken titel zonder eigen plaats vast aan de bovenkant, de eerste regel waar hij stond', () => {
    const { title } = titelOpBreedte(titel, 268, 32)
    expect(title).toMatchObject({ yref: 'container', y: 1, yanchor: 'top' })
    expect(title.pad.t).toBeCloseTo(16)
  })

  it('houdt plaats en ondertitel van een titel met noot, met de kaphoogte terug als pad', () => {
    const metNoot = {
      ...titel, yref: 'container', yanchor: 'top', y: 0.98,
      subtitle: { text: 'De aantallen zijn afgerond<br>op 10-tallen.', font: { size: 11, color: '#666' } },
    }
    const { title } = titelOpBreedte(metNoot, 268, 100)
    expect(title).toMatchObject({ yref: 'container', yanchor: 'top', y: 0.98, subtitle: metNoot.subtitle })
    expect(title.pad.t).toBeCloseTo(0.7 * 16)
    expect(titelOpBreedte({ ...metNoot, pad: { t: 2, l: 4 } }, 268, 100).title.pad).toEqual({ t: 2 + 0.7 * 16, l: 4 })
  })

  it('laat een titel met een eigen plaats die niet aan de bovenkant hangt op zijn plaats', () => {
    const onder = { ...titel, yref: 'paper', y: 1, yanchor: 'bottom' }
    const { title } = titelOpBreedte(onder, 268, 32)
    expect(title).toMatchObject({ yref: 'paper', y: 1, yanchor: 'bottom' })
    expect(title.pad).toBeUndefined()
  })

  it('verandert het titelobject zelf niet', () => {
    const kopie = structuredClone(titel)
    titelOpBreedte(titel, 268, 32)
    expect(titel).toEqual(kopie)
  })

  it('reserveert ook ruimte voor een bestaande <br> als de breedte bekend is', () => {
    const { title, extra } = titelOpBreedte({ text: 'Twee<br>regels' }, 1200, 32)
    expect(title.text).toBe('Twee<br>regels')
    expect(extra).toBeCloseTo(16 * 1.3)
  })
})

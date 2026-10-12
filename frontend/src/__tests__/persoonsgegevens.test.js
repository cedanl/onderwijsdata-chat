// #478: persoonsgegevens in de invoer herkennen (elfproef, e-mail, telefoon), in code.
import { describe, it, expect } from 'vitest'
import { bevatPersoonsgegevens, elfproef, persoonsgegevensMelding, vindPersoonsgegevens } from '../persoonsgegevens'
import { conversationTitle, TITEL_ZONDER_PERSOONSGEGEVENS } from '../conversationTitle'

describe('elfproef', () => {
  it('herkent een geldig BSN', () => {
    expect(elfproef('123456782')).toBe(true)
    expect(elfproef('111222333')).toBe(true)
  })

  it('wijst een ander getal af', () => {
    for (const geen of ['123456789', '000000000', '12345678', '1234567890', '85423NED']) expect(elfproef(geen)).toBe(false)
  })
})

describe('vindPersoonsgegevens', () => {
  it('vindt BSN, e-mailadres en telefoonnummer in volgorde', () => {
    const tekst = 'Mijn naam is Test Persoon, mijn BSN is 123456782, mail test@voorbeeld.nl of bel 06-12345678.'
    expect(vindPersoonsgegevens(tekst)).toEqual([
      { soort: 'bsn', tekst: '123456782' },
      { soort: 'email', tekst: 'test@voorbeeld.nl' },
      { soort: 'telefoon', tekst: '06-12345678' },
    ])
  })

  it('laat gewone onderwijsvragen met rust', () => {
    for (const tekst of [
      'Hoeveel studenten had de HU in 2024/25 bij opleiding 36201?',
      'CBS-tabel 85423NED, code A025297, instelling 21PL',
      'In totaal 123456789 euro, en 1.234.567.890 inschrijvingen',
      'Bel 0800 1234 of kijk op onderwijsdata.nl',
      '',
      null,
    ]) expect(bevatPersoonsgegevens(tekst)).toBe(false)
  })

  it('herkent Nederlandse telefoonnummers', () => {
    for (const t of ['0612345678', '06 12345678', '030-1234567', '+31 6 12345678', '0031612345678']) {
      expect(vindPersoonsgegevens(`bel me op ${t} graag`)).toEqual([{ soort: 'telefoon', tekst: t }])
    }
  })
})

describe('persoonsgegevensMelding', () => {
  it('noemt wat er gevonden is', () => {
    expect(persoonsgegevensMelding('BSN 123456782')).toContain('een BSN')
    expect(persoonsgegevensMelding('BSN 123456782, test@voorbeeld.nl')).toContain('een BSN en een e-mailadres')
    expect(persoonsgegevensMelding('hoeveel studenten?')).toBeNull()
  })
})

describe('conversationTitle zonder persoonsgegevens', () => {
  it('geeft een generieke titel als de vraag een BSN, e-mailadres of telefoonnummer bevat', () => {
    const vraag = 'Mijn naam is Test Persoon, mijn BSN is 123456782, kun je zoeken hoeveel studenten de HU heeft?'
    expect(conversationTitle(vraag)).toBe(TITEL_ZONDER_PERSOONSGEGEVENS)
    expect(conversationTitle('mail test@voorbeeld.nl')).toBe(TITEL_ZONDER_PERSOONSGEGEVENS)
  })

  it('houdt een gewone vraag als titel', () => {
    expect(conversationTitle('Hoeveel studenten heeft de HU in 2024/25?')).toBe('Hoeveel studenten heeft de HU in 2024/25?')
  })
})

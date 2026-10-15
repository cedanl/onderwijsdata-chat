// #544: de CSV-knop onder een dataantwoord hangt niet af van welke tool het model koos. Zonder tabel-key
// van de server zijn de geciteerde getallen de export, gebouwd uit de citaties die het antwoord draagt.
import { describe, it, expect } from 'vitest'
import { CITATIE_CSV_BESTAND, citatieRijen, citatiesToCsv } from '../citatieCsv'
import { hasExport } from '../dataExport'

const DUO = 'DUO · Ingeschrevenen hoger onderwijs (p01hoinges)'
const cite = (getal, extra = {}) => ({
  getal, vastgesteld: true, stap: 2, tool: 'compute_kpi', label: 'KPI berekend', bron: DUO, maat: 'Aantal', ...extra,
})

describe('citatiesToCsv', () => {
  it('zet per geciteerd getal maat, eenheid, selectie, bron en stap in een rij, in tekstvolgorde', () => {
    const csv = citatiesToCsv([
      cite('36.206', { selectie: '2023/24 · Hogeschool Utrecht', eenheid: 'studenten' }),
      cite('37.500', { selectie: '2024/25 · HAN', stap: 3 }),
    ])
    expect(csv.split('\n')).toEqual([
      '# cijfers uit het antwoord, zoals geschreven, met de herkomst per getal',
      'getal;maat;eenheid;selectie;bron;stap',
      `36.206;Aantal;studenten;2023/24 · Hogeschool Utrecht;${DUO};2`,
      `37.500;Aantal;;2024/25 · HAN;${DUO};3`,
    ])
  })

  it('laat een getal zonder vastgestelde herkomst weg en zegt dat erboven', () => {
    const csv = citatiesToCsv([cite('7.912'), { getal: '8.304', vastgesteld: false, reden: 'geen_meetwaarde' }])
    expect(csv).toContain('# 1 getal zonder vastgestelde herkomst weggelaten')
    expect(csv).not.toContain('8.304')
    expect(csv.split('\n').at(-1)).toBe(`7.912;Aantal;;;${DUO};2`)
  })

  it('geeft niets zonder vastgesteld getal', () => {
    expect(citatiesToCsv([])).toBeNull()
    expect(citatiesToCsv(undefined)).toBeNull()
    expect(citatiesToCsv([{ getal: '1', vastgesteld: false }])).toBeNull()
    expect(citatieRijen(null)).toEqual([])
  })

  it('beschermt tekst die Excel als formule zou lezen (#483) en citeert een puntkomma', () => {
    const csv = citatiesToCsv([cite('-5', { selectie: '=SOM(A1)', bron: 'DUO; Avans' })])
    expect(csv.split('\n').at(-1)).toBe(`-5;Aantal;;'=SOM(A1);"DUO; Avans";2`)
  })

  it('heeft een vaste bestandsnaam', () => {
    expect(CITATIE_CSV_BESTAND).toBe('cijfers_antwoord.csv')
  })
})

describe('hasExport', () => {
  const stap = exportKey => ({ name: 'query_data', done: true, exportKey })

  it('is waar met een tabel-key van de server, ook zonder citaties', () => {
    expect(hasExport({ tools: [stap('duo:x:0:ab')], citaties: [] })).toBe(true)
  })

  it('is waar met alleen geciteerde getallen: de knop hangt niet van de tool af', () => {
    expect(hasExport({ tools: [{ name: 'compute_kpi', done: true, exportKey: null }], citaties: [cite('36.206')] })).toBe(true)
  })

  it('is onwaar zonder tabel en zonder vastgesteld getal', () => {
    expect(hasExport({ tools: [], citaties: [{ getal: '1', vastgesteld: false }] })).toBe(false)
    expect(hasExport({})).toBe(false)
    expect(hasExport(null)).toBe(false)
  })
})

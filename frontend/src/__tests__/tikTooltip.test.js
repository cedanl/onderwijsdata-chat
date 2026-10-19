// #614: op een telefoon gaf een tik op een staaf of punt geen waarde. De chatlayout zet nu de tooltip op het
// dichtstbijzijnde punt binnen 40 px, zet op een smal scherm de sleepzoom uit (die at de tik op) en geeft
// de tooltip de kleuren van het thema.
import { describe, it, expect } from 'vitest'
import { chatFigureLayout, HOVER_DISTANCE, TOUCH_WIDTH } from '../figureLayout'

const fig = { data: [{ type: 'bar', x: [2023, 2024], y: [1, 2] }], layout: { title: { text: 'Studenten' } } }

describe('tikbare waardetooltip', () => {
  it('zet op een telefoon de sleepzoom uit en de tooltip op het dichtstbijzijnde punt', () => {
    const layout = chatFigureLayout(fig, false, 390)
    expect(layout).toMatchObject({ hovermode: 'closest', hoverdistance: HOVER_DISTANCE, dragmode: false })
    expect(HOVER_DISTANCE).toBeGreaterThanOrEqual(40)
  })

  it('laat op een breed scherm de sleepzoom staan', () => {
    expect(chatFigureLayout(fig, false, TOUCH_WIDTH + 1)).not.toHaveProperty('dragmode')
    // Breedte nog onbekend (vóór het meten): ook niet uitzetten.
    expect(chatFigureLayout(fig, false, 0)).not.toHaveProperty('dragmode')
  })

  it('geeft de tooltip de kleuren van het thema', () => {
    const licht = chatFigureLayout(fig, false, 390).hoverlabel
    const donker = chatFigureLayout(fig, true, 390).hoverlabel
    expect(licht.bgcolor).not.toBe(donker.bgcolor)
    expect(licht.font.color).not.toBe(donker.font.color)
    expect(donker.font.size).toBeGreaterThanOrEqual(13)
  })
})

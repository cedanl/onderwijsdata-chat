// #568: the app's theme choice travels into the sandboxed report frame as a class on <html>.
import { describe, it, expect } from 'vitest'
import { metThema } from '../reportThema'

const RAPPORT = '<!DOCTYPE html><html lang="nl"><head><title>R</title></head><body><p>rapport</p></body></html>'

describe('metThema (#568)', () => {
  it.each([['dark'], ['light']])('zet de klasse %s op <html> voor een expliciete keuze', mode => {
    expect(metThema(RAPPORT, mode)).toBe(RAPPORT.replace('<html lang="nl">', `<html lang="nl" class="${mode}">`))
  })

  it.each([['system'], [undefined], [null], ['']])('laat het rapport met rust bij modus %j: dan beslist de OS-voorkeur', mode => {
    expect(metThema(RAPPORT, mode)).toBe(RAPPORT)
  })

  it('laat lege HTML met rust', () => {
    expect(metThema('', 'dark')).toBe('')
    expect(metThema(null, 'dark')).toBeNull()
    expect(metThema(undefined, 'dark')).toBeUndefined()
  })

  it('werkt ook op een kale <html> zonder attributen en op hoofdletters', () => {
    expect(metThema('<html><body>r</body></html>', 'dark')).toBe('<html class="dark"><body>r</body></html>')
    expect(metThema('<HTML LANG="nl"><body>r</body></HTML>', 'light')).toBe('<HTML LANG="nl" class="light"><body>r</body></HTML>')
  })

  it('vervangt een eerdere themaklasse en houdt andere klassen', () => {
    const html = '<html lang="nl" class="dark print"><body>r</body></html>'
    expect(metThema(html, 'light')).toBe('<html lang="nl" class="print light"><body>r</body></html>')
    expect(metThema(metThema(RAPPORT, 'dark'), 'dark')).toBe(metThema(RAPPORT, 'dark'))
  })

  it('raakt alleen de eerste <html>-tag, niet tekst verderop', () => {
    const html = `${RAPPORT}<p>&lt;html&gt; <html>in tekst</html></p>`
    expect(metThema(html, 'dark').split('class="dark"')).toHaveLength(2)
  })

  it('laat HTML zonder <html>-tag ongemoeid', () => {
    expect(metThema('<head></head><p>rapport</p>', 'dark')).toBe('<head></head><p>rapport</p>')
  })
})

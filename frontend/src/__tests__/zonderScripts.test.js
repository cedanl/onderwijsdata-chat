// #654: a report thumbnail runs in sandbox="" and blocks every script; each one put a "Blocked script execution"
// line in the console. The thumbnail gets the report without its <script> blocks.
import { describe, it, expect } from 'vitest'
import { zonderScripts } from '../zonderScripts'

describe('zonderScripts', () => {
  it('removes an inline script and leaves the rest as it was', () => {
    expect(zonderScripts('<h1>Instroom</h1><script>Plotly.newPlot(e, d)</script><p>Tekst</p>'))
      .toBe('<h1>Instroom</h1><p>Tekst</p>')
  })

  it('removes every block: any case, with attributes, src= and over several lines', () => {
    const html = [
      '<html class="dark"><head>',
      '<SCRIPT SRC="/plotly.min.js"></SCRIPT>',
      '<script type="text/javascript" data-x="1">',
      '  var f = {"a": 1};',
      '  Plotly.newPlot(f)',
      '</script >',
      '<style>h1{color:red}</style></head>',
      '<body><div id="fig"></div><Script>window.print()</sCrIpT></body></html>',
    ].join('\n')
    const uit = zonderScripts(html)
    expect(uit).not.toMatch(/<script/i)
    expect(uit).not.toMatch(/Plotly|window\.print/)
    expect(uit).toBe('<html class="dark"><head>\n\n\n<style>h1{color:red}</style></head>\n<body><div id="fig"></div></body></html>')
  })

  it('removes an unterminated script up to the end', () => {
    expect(zonderScripts('<h1>Kop</h1><script>var a = 1;\n<p>nooit HTML</p>')).toBe('<h1>Kop</h1>')
  })

  it('keeps an element whose name only starts with "script"', () => {
    expect(zonderScripts('<script-kaart>Kaart</script-kaart><p>Tekst</p>')).toBe('<script-kaart>Kaart</script-kaart><p>Tekst</p>')
  })

  it('leaves HTML without scripts and an empty value alone', () => {
    expect(zonderScripts('<p>Geen scripts</p>')).toBe('<p>Geen scripts</p>')
    expect(zonderScripts(null)).toBeNull()
    expect(zonderScripts('')).toBe('')
  })
})

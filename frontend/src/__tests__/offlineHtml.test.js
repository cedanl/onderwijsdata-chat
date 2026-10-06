import { describe, it, expect, vi } from 'vitest'
import { inlinePlotly } from '../offlineHtml'

const CDN = '<script src="https://cdn.plot.ly/plotly-4.1.0.min.js"></script>'

describe('inlinePlotly (#405, UX N11)', () => {
  it('vervangt de CDN-verwijzing door de meegeleverde Plotly', async () => {
    const html = await inlinePlotly(`<head>${CDN}</head><div id="a"></div>`, async () => 'window.Plotly={}')
    expect(html).not.toContain('cdn.plot.ly')
    expect(html).toBe('<head><script>window.Plotly={}</script></head><div id="a"></div>')
  })

  it('neemt Plotly één keer op, ook als elke grafiek de CDN noemde', async () => {
    const html = await inlinePlotly(`${CDN}<div id="a"></div>${CDN}<div id="b"></div>`, async () => 'P')
    expect(html).toBe('<script>P</script><div id="a"></div><div id="b"></div>')
  })

  it('laadt Plotly niet voor een bestand zonder grafiek', async () => {
    const load = vi.fn()
    expect(await inlinePlotly('<p>alleen tekst</p>', load)).toBe('<p>alleen tekst</p>')
    expect(load).not.toHaveBeenCalled()
  })

  it('breekt het script-element niet af op een </script> in de broncode', async () => {
    const html = await inlinePlotly(CDN, async () => 'var s="</script>"')
    expect(html).toBe('<script>var s="<\\/script>"</script>')
  })
})

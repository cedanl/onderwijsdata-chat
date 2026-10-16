// Shared by the report and dashboard HTML tests (#567, #574); not a test file itself.
import { JSDOM, VirtualConsole } from 'jsdom'

// Loads generated HTML in a fresh DOM that runs its inline scripts, with Plotly, the
// dialogs and matchMedia stubbed, and records what the page did. `dark` answers the
// prefers-color-scheme query; `width` is the window width (jsdom's 1024 by default).
export function runPage(html, { dark = false, width = 1024 } = {}) {
  const seen = { dialogs: [], plots: [], errors: [] }
  const virtualConsole = new VirtualConsole()
  virtualConsole.on('jsdomError', err => seen.errors.push(err.message))
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    virtualConsole,
    beforeParse(window) {
      for (const name of ['alert', 'confirm', 'prompt']) window[name] = (...args) => seen.dialogs.push([name, ...args])
      window.matchMedia = () => ({ matches: dark })
      window.innerWidth = width
      window.Plotly = { newPlot: (el, ...args) => seen.plots.push([el.id ?? el, ...args]) }
    },
  })
  seen.images = dom.window.document.querySelectorAll('img').length
  dom.window.close()
  return seen
}

// Like runPage, but Plotly reports a plot area of `plotH` px in a figure of 420 px and resolves its promise, so
// what the page does after drawing (#579: the plot area grows on a phone) runs too. Records the relayouts and
// the height the chart div ends up with.
export async function runPageNaTekenen(html, { width = 390, plotH }) {
  const seen = { relayout: [], errors: [] }
  const virtualConsole = new VirtualConsole()
  virtualConsole.on('jsdomError', err => seen.errors.push(err.message))
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    virtualConsole,
    beforeParse(window) {
      window.matchMedia = () => ({ matches: false })
      window.innerWidth = width
      window.Plotly = {
        newPlot: el => {
          el.getBoundingClientRect = () => ({ width: width - 32, height: 420 })
          el._fullLayout = { _size: { h: plotH } }
          return Promise.resolve(el)
        },
        relayout: (el, update) => {
          seen.relayout.push(update)
          return Promise.resolve(el)
        },
      }
    },
  })
  await new Promise(resolve => setTimeout(resolve, 0))
  seen.height = dom.window.document.getElementById('rp0').style.height
  dom.window.close()
  return seen
}

// WCAG relative luminance and contrast ratio of #RRGGBB colours.
export function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

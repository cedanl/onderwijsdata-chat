// Explicit choices get their own class, so the prefers-color-scheme fallback
// in styles.css (html:not(.dark):not(.light)) only applies before this runs
// or in system mode.
// De statusbalk van een geïnstalleerde app (#672): de kleur van de navbar in het thema dat de gebruiker koos. Zonder
// keuze ('system') houdt elke meta zijn eigen kleur voor zijn media-query, zoals index.html ze zet.
export const THEME_COLOR = { light: '#FFFFFF', dark: '#1A1F2E' }

function zetThemeColor(mode, isDark) {
  for (const meta of document.querySelectorAll('meta[name="theme-color"]')) {
    const voorDonker = mode === 'system' ? (meta.getAttribute('media') || '').includes('dark') : isDark
    meta.setAttribute('content', THEME_COLOR[voorDonker ? 'dark' : 'light'])
  }
}

export function applyMode(mode) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = mode === 'dark' || (mode === 'system' && prefersDark)
  document.documentElement.classList.toggle('dark', isDark)
  document.documentElement.classList.toggle('light', mode === 'light')
  zetThemeColor(mode, isDark)
}

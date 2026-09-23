// Explicit choices get their own class, so the prefers-color-scheme fallback
// in styles.css (html:not(.dark):not(.light)) only applies before this runs
// or in system mode.
export function applyMode(mode) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = mode === 'dark' || (mode === 'system' && prefersDark)
  document.documentElement.classList.toggle('dark', isDark)
  document.documentElement.classList.toggle('light', mode === 'light')
}

// Eerste focusbare element van de app (#687, WCAG 2.4.1): met het toetsenbord of een schermlezer meteen naar de
// inhoud, zonder eerst door de navigatie. De klik zet de focus zelf op <main>: een kale #main zou de URL veranderen
// en via de router een navigatie geven.
export const MAIN_ID = 'main'

export default function SkipLink() {
  const naarInhoud = (event) => {
    const main = document.getElementById(MAIN_ID)
    if (!main) return
    event.preventDefault()
    main.focus()
    main.scrollIntoView?.()
  }
  return <a className="skip-link" href={`#${MAIN_ID}`} onClick={naarInhoud}>Naar de inhoud</a>
}

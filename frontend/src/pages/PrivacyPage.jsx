import { useDocumentTitle, pageTitle } from '../hooks/useDocumentTitle'
import PrivacyInhoud from '../components/PrivacyInhoud'

// De privacy-informatie als volledige pagina (#477): App.jsx toont haar ook zonder sessie, en docs en
// SECURITY.md linken naar /privacy. De tekst zelf staat in PrivacyInhoud, die ook de popup toont (#572).
export { PRIVACY_KOPJES } from '../components/PrivacyInhoud'

export default function PrivacyPage({ standalone = false }) {
  useDocumentTitle(pageTitle('Privacy'))
  return (
    <article className={`privacy-page${standalone ? ' privacy-page--standalone' : ''}`}>
      <PrivacyInhoud />
      <p className="privacy-page-footer">
        <a href="/" className="notfound-link">{standalone ? 'Naar het inloggen' : 'Terug naar de startpagina'}</a>
      </p>
    </article>
  )
}

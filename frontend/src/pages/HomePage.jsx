import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import DataSourcesModal from '../components/DataSourcesModal'

export default function HomePage({ dashboardsEnabled = true }) {
  const navigate = useNavigate()
  const [showSources, setShowSources] = useState(false)
  return (
    <div>
      {/* Hero */}
      <section className="hero">
        <div className="container">
          <div className="hero-content">
            <h1>Van open onderwijsdata naar <em>reproduceerbare inzichten in seconden</em></h1>
            <p>openEDUdata+ koppelt en harmoniseert alle open-onderwijs-databronnen alvast voor je. Stel een ad-hoc vraag over instroom, voortgang, arbeidsmarkt of diplomering en krijg binnen 30 seconden een onderbouwd, herleidbaar antwoord.</p>
            <div className="hero-actions">
              <button type="button" className="btn-primary" onClick={() => navigate('/chat')}>Probeer de chat →</button>
              {dashboardsEnabled && (
                <>
                  <span style={{ color: 'rgba(255,255,255,.5)', fontSize: '0.9rem', alignSelf: 'center' }}>of</span>
                  <button type="button" className="btn-ghost" onClick={() => navigate('/dashboards')}>Maak een dashboard</button>
                </>
              )}
            </div>
            <div className="hero-stats">
              <div><div className="hero-stat-value">30s</div><div className="hero-stat-label">Gemiddelde responstijd</div></div>
              <div><div className="hero-stat-value">120+</div><div className="hero-stat-label">Datasets gekoppeld</div></div>
              <div><div className="hero-stat-value">100%</div><div className="hero-stat-label">Open onderwijsdata</div></div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="section">
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <div className="section-label">Functionaliteit</div>
            <h2 className="section-title">Geen databewerking, wel controle</h2>
            <p className="section-sub" style={{ margin: '0 auto' }}>Eén bron voor alle onderwijsvragen. Al gekoppeld, al geharmoniseerd, altijd herleidbaar naar de brondata.</p>
          </div>
          <div className="grid grid-2 gap-6">
            <div className="feature-card">
              <div className="feature-icon blue">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
              </div>
              <h3>Al gekoppeld en geharmoniseerd</h3>
              <p>Geen ETL, geen matching-werk, geen definitieverschillen tussen bronnen. De datasets zijn samengevoegd en klaar voor analyse.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon teal">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              </div>
              <h3>Ad-hoc vragen in seconden</h3>
              <p>Stel je vraag in gewone taal, krijg direct antwoord. Geen wachtrij voor een dashboard dat eerst gebouwd moet worden.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon purple">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              </div>
              <h3>Reproduceerbare, uitlegbare methodiek</h3>
              <p>Elk antwoord toont welke bronnen zijn gebruikt en hoe de berekening tot stand kwam. Verdedigbaar tegenover auditors en bestuur, en zelf te reproduceren.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon blue">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </div>
              <h3>Ruwe data, jouw analyse</h3>
              <p>Volledige controle over de onderliggende data. Exporteer wat je nodig hebt en stel je eigen analyse samen, geen black box.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="section" style={{ background: 'var(--gray-50)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <div className="section-label">Voordelen</div>
            <h2 className="section-title">Waarom IR-dataprofessionals openEDUdata+ gebruiken</h2>
          </div>
          <div className="grid grid-2 gap-4">
            {[
              { icon: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>, title: 'Tijd terug', desc: 'Geen weken kwijt aan koppelen en opschonen. De cijfers staan klaar, direct inzetbaar voor jouw analyse.' },
              { icon: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />, title: 'Verdedigbare cijfers', desc: 'Reproduceerbare methodiek met volledige bronvermelding. Bestand tegen vragen van auditors, accountants en bestuur.' },
              { icon: <><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" /></>, title: 'Eén brontabel voor iedereen', desc: "Instelling, management en collega-IR'ers werken met exact dezelfde geharmoniseerde cijfers. Geen discussie over wiens versie klopt." },
              { icon: <><line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" /><line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" /><line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" /><line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" /><line x1="17" y1="16" x2="23" y2="16" /></>, title: 'Zelf aan het stuur', desc: 'Ruwe, gekoppelde data beschikbaar voor eigen modellen en analyses. Geen afhankelijkheid van een vaste rapportagevorm.' },
            ].map(({ icon, title, desc }) => (
              <div key={title} className="benefit-card">
                <div className="benefit-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{icon}</svg>
                </div>
                <div><h3>{title}</h3><p>{desc}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <div className="container">
          <h2>Klaar om te beginnen?</h2>
          <p>Stel je eerste vraag aan openEDUdata+ en ontdek wat gekoppelde open onderwijsdata voor jouw analyses betekent.</p>
          <button type="button" className="btn-primary" onClick={() => navigate('/chat')}>Start de chat →</button>
        </div>
      </section>

      <footer style={{ background: 'var(--white)', borderTop: '1px solid var(--gray-200)', padding: '32px 0' }}>
        <div className="container" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="navbar-brand">
              <div className="navbar-logo" style={{ width: 28, height: 28 }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                  <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
                </svg>
              </div>
              <span className="navbar-name" style={{ fontSize: '1rem' }}>openEDU<span>data+</span></span>
            </div>
            <button type="button" className="sources-link" onClick={() => setShowSources(true)}>
              Gebaseerd op open onderwijsdata
            </button>
          </div>
          <p style={{ fontSize: '.75rem', color: 'var(--gray-400)', lineHeight: 1.6, borderTop: '1px solid var(--gray-100)', paddingTop: 12, margin: 0, textAlign: 'center' }}>
            Op deze tool is de{' '}
            <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.nl" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--gray-400)', textDecoration: 'underline' }}>
              Creative Commons ShareAlike Naamsvermelding 4.0-licentie
            </a>
            {' '}van toepassing.<br />Maak bij gebruik van dit werk vermelding van de volgende referentie:{' '}
            <em>AI en data waarde(n)vol inzetten: CEDA. openEDUdata+. Utrecht: Npuls</em>
          </p>
        </div>
      </footer>

      {showSources && <DataSourcesModal onClose={() => setShowSources(false)} />}
    </div>
  )
}

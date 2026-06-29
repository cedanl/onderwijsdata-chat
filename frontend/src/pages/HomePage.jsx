import { useState } from 'react'

export default function HomePage({ setPage }) {
  const [showSources, setShowSources] = useState(false)
  return (
    <div>
      {/* Hero */}
      <section className="hero">
        <div className="container">
          <div className="hero-content">
            <h1>Van open onderwijsdata naar <em>inzicht in seconden</em></h1>
            <p>openEDUdata+ koppelt aan alle open-onderwijs-databronnen. Stel een vraag in gewone taal over instroom, voortgang, arbeidsmarkt of diplomering en krijg binnen 30 seconden een onderbouwd antwoord.</p>
            <div className="hero-actions">
              <button className="btn-primary" onClick={() => setPage('chat')}>Probeer de chat →</button>
              <span style={{ color: 'rgba(255,255,255,.5)', fontSize: '0.9rem', alignSelf: 'center' }}>of</span>
              <button className="btn-ghost" onClick={() => setPage('dashboard')}>Maak een dashboard</button>
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
            <h2 className="section-title">Van vraag naar inzicht</h2>
            <p className="section-sub" style={{ margin: '0 auto' }}>Eén assistent voor alle onderwijsvragen. Van instroom tot diplomering, altijd onderbouwd en uitlegbaar.</p>
          </div>
          <div className="grid grid-3 gap-6">
            <div className="feature-card">
              <div className="feature-icon blue">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              </div>
              <h3>Stel vragen in gewone taal</h3>
              <p>Typ je vraag zoals je die zou stellen aan een collega. openEDUdata+ begrijpt de context en haalt het juiste antwoord op.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon teal">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
              </div>
              <h3>Dashboards zonder BI-kennis</h3>
              <p>Beschrijf wat je wilt zien. openEDUdata+ bouwt automatisch de juiste grafiek en koppelt deze aan de juiste databron.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon purple">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              </div>
              <h3>Uitlegbare inzichten</h3>
              <p>Elk antwoord toont welke bronnen zijn gebruikt en hoe de conclusie tot stand kwam. Controleerbaar, en altijd terug te herleiden naar de data.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="section" style={{ background: 'var(--gray-50)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <div className="section-label">Voordelen</div>
            <h2 className="section-title">Waarom je van openEDUdata+ gaat houden</h2>
          </div>
          <div className="grid grid-2 gap-4">
            {[
              { icon: <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />, title: 'Direct inzichten', desc: 'Je AI-assistent beantwoordt al je onderwijsvragen in een handomdraai. Zo win je kostbare tijd.' },
              { icon: <><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></>, title: 'Dashboards op maat', desc: 'Direct een helder dashboard laat genereren: van management tot bestuur krijgt direct visueel inzicht op maat.' },
              { icon: <><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" /></>, title: 'Beslissen op feiten', desc: 'De assistent laat je in één oogopslag zien wat er speelt, waar kansen liggen en wat de beste volgende stap is.' },
              { icon: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />, title: 'Altijd één waarheid', desc: 'Iedereen werkt altijd met exact dezelfde cijfers. Geen misverstanden of discussies over verschillende versies.' },
            ].map(({ icon, title, desc }, i) => (
              <div key={i} className="benefit-card">
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
          <p>Stel je eerste vraag aan openEDUdata+ en ontdek wat open onderwijsdata voor jouw organisatie kan betekenen.</p>
          <button className="btn-primary" onClick={() => setPage('chat')}>Start de chat →</button>
        </div>
      </section>

      <footer style={{ background: 'var(--white)', borderTop: '1px solid var(--gray-200)', padding: '32px 0' }}>
        <div className="container flex justify-between items-center">
          <div className="navbar-brand">
            <div className="navbar-logo" style={{ width: 28, height: 28 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
              </svg>
            </div>
            <span className="navbar-name" style={{ fontSize: '1rem' }}>openEDU<span>data+</span></span>
          </div>
          <button className="sources-link" onClick={() => setShowSources(true)}>
            Gebaseerd op open onderwijsdata
          </button>
        </div>
      </footer>

      {showSources && (
        <div className="modal-overlay" onClick={() => setShowSources(false)}>
          <button className="modal-overlay-close" onClick={() => setShowSources(false)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 20, height: 20 }}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <div className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
              <div>
                <div className="section-label" style={{ marginBottom: 4 }}>Transparantie</div>
                <h2>Databronnen</h2>
              </div>
            </div>
            <div className="modal-body">
              <table className="modal-table">
                <thead>
                  <tr>
                    <th>Bron</th>
                    <th>Inhoud</th>
                    <th>Catalogus</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['CBS', '68 datasets met onderwijsstatistieken', 'cedanl.github.io/cbs-onderwijsdata', 'https://cedanl.github.io/cbs-onderwijsdata'],
                    ['RIO', 'Register van onderwijsinstellingen en opleidingen (14 resources)', 'cedanl.github.io/rio-onderwijsdata', 'https://cedanl.github.io/rio-onderwijsdata'],
                    ['DUO', '57 open datasets: prognoses, diplomering, instroom, adressen', 'onderwijsdata.duo.nl', 'https://onderwijsdata.duo.nl'],
                  ].map(([bron, inhoud, catalogus, href]) => (
                    <tr key={bron}>
                      <td><span className="source-name">{bron}</span></td>
                      <td><span className="source-desc">{inhoud}</span></td>
                      <td><a href={href} target="_blank" rel="noreferrer">{catalogus}</a></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

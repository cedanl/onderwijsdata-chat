export default function HomePage({ setPage }) {
  return (
    <div>
      {/* Hero */}
      <section className="hero">
        <div className="container">
          <div className="hero-content">
            <div className="hero-badge">
              <div className="hero-badge-dot" />
              Open onderwijsdata · AI-gedreven
            </div>
            <h1>Van onderwijsdata naar<br /><em>inzicht in seconden</em></h1>
            <p>EDUdata koppelt aan alle open-onderwijs-databronnen. Vraag wat je wilt weten over instroom, voortgang, arbeidsmarkt of diplomering. Antwoord in 30 seconden.</p>
            <div className="hero-actions">
              <button className="btn-primary" onClick={() => setPage('chat')}>Probeer de chat →</button>
              <button className="btn-ghost" onClick={() => setPage('dashboard')}>Bekijk dashboard</button>
            </div>
            <div className="hero-stats">
              <div><div className="hero-stat-value">30s</div><div className="hero-stat-label">Gemiddelde responstijd</div></div>
              <div><div className="hero-stat-value">40+</div><div className="hero-stat-label">Databronnen gekoppeld</div></div>
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
            <h2 className="section-title">Alles wat je nodig hebt,<br />niets wat je niet nodig hebt</h2>
            <p className="section-sub" style={{ margin: '0 auto' }}>Eén assistent voor alle onderwijsvragen. Van instroom tot diplomering — altijd onderbouwd en uitlegbaar.</p>
          </div>
          <div className="grid grid-3 gap-6">
            <div className="feature-card">
              <div className="feature-icon blue">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
              </div>
              <h3>Stel vragen in gewone taal</h3>
              <p>Geen SQL, geen BI-tool. Typ je vraag zoals je die zou stellen aan een collega. EDUdata begrijpt de context en haalt het juiste antwoord op.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon teal">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>
              </div>
              <h3>Dashboards zonder BI-kennis</h3>
              <p>Beschrijf wat je wilt zien. EDUdata bouwt automatisch de juiste grafiek of tegel en koppelt deze aan de juiste databron. Altijd up-to-date.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon purple">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
              </div>
              <h3>Uitlegbare inzichten</h3>
              <p>Elk antwoord toont welke bronnen zijn gebruikt en hoe de conclusie tot stand kwam. Controleerbaar, deelbaar en altijd terug te herleiden naar de data.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Steps */}
      <section className="section steps-section">
        <div className="container">
          <div style={{ marginBottom: 40 }}>
            <div className="section-label">Zo werkt het</div>
            <h2 className="section-title">Van vraag naar inzicht in 3 stappen</h2>
          </div>
          <div className="grid grid-3 gap-6">
            <div className="step-card">
              <div className="step-number">1</div>
              <h3>Werkt met open onderwijsdata</h3>
              <p>EDUdata verbindt met DUO, CBS, OECD, 1cijferHO en andere open bronnen. De data blijft waar die staat — EDUdata leest mee en vormt één betrouwbaar beeld.</p>
            </div>
            <div className="step-card">
              <div className="step-number">2</div>
              <h3>Simpel vragen; EDUdata doet de analyse</h3>
              <p>Typ of spreek je vraag in gewone taal. EDUdata zoekt in de data, legt verbanden en doet de berekeningen. Het antwoord komt als tekst, tabel of grafiek.</p>
            </div>
            <div className="step-card">
              <div className="step-number">3</div>
              <h3>Inzicht met context en bronnen</h3>
              <p>Je krijgt niet alleen een antwoord, maar ook de toelichting: welke databron, welk tijdvak, welke trend. Alles herleidbaar en deelbaar met je team.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Comparison */}
      <section className="section">
        <div className="container">
          <div style={{ marginBottom: 40, textAlign: 'center' }}>
            <div className="section-label">Vergelijking</div>
            <h2 className="section-title">Stop met werken op de logica van gisteren</h2>
            <p className="section-sub" style={{ margin: '0 auto' }}>Met EDUdata werk je op de logica van morgen: actuele inzichten uit open onderwijsdata, direct beschikbaar voor iedereen.</p>
          </div>
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Vóór EDUdata</th>
                <th>✦ Met EDUdata</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['4 systemen, 4 logins, 4 antwoorden', '1 vraag, 1 antwoord, 1 plek'],
                ['Dashboards na 3 dagen', 'Antwoord in 30 seconden'],
                ['Beslissen op data van 2 weken oud', 'Beslissen op data van vandaag'],
                ['Grote kans op fouten', 'Betrouwbare data & controleerbare AI'],
                ['Handmatig werken', 'Directe AI-optimalisatie'],
              ].map(([before, after], i) => (
                <tr key={i}>
                  <td><span className="cross-icon">✗</span>{before}</td>
                  <td><span className="check-icon">✓</span>{after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Benefits */}
      <section className="section" style={{ background: 'var(--gray-50)' }}>
        <div className="container">
          <div style={{ marginBottom: 40 }}>
            <div className="section-label">Voordelen</div>
            <h2 className="section-title">Waarom je van EDUdata gaat houden</h2>
          </div>
          <div className="grid grid-2 gap-4">
            {[
              { icon: <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />, title: 'Minder handwerk, meer output', desc: 'EDUdata automatiseert terugkerende taken. Teams winnen tijd voor werk met impact.' },
              { icon: <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>, title: 'Direct inzicht voor iedereen', desc: 'Elke rol krijgt relevante antwoorden en dashboards op maat — van docent tot bestuur.' },
              { icon: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />, title: 'Altijd één waarheid', desc: 'Alle systemen gekoppeld = dezelfde cijfers voor iedereen. Geen discussie over versies of bronnen.' },
              { icon: <><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" /></>, title: 'Beslissen op feiten', desc: "Je ziet wat er speelt en waar kansen liggen — onderbouwd met actuele open onderwijsdata." },
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

      <footer style={{ background: 'var(--white)', borderTop: '1px solid var(--gray-200)', padding: '32px 0' }}>
        <div className="container flex justify-between items-center">
          <div className="navbar-brand">
            <div className="navbar-logo" style={{ width: 28, height: 28 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className="navbar-name" style={{ fontSize: '1rem' }}>EDU<span>data</span></span>
          </div>
          <span className="text-sm text-muted">© 2025 EDUdata. Gebaseerd op open onderwijsdata.</span>
        </div>
      </footer>
    </div>
  )
}

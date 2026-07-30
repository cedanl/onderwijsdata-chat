// ─── Shell ──────────────────────────────────────────────────────────────────

export function DashboardShell({ instelling, children, loading, data, error }) {
  if (loading) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Data laden&hellip;</span>
        </div>
        <div className="db-skeleton-grid">
          {[1,2,3,4].map(n => <div key={n} className="db-skeleton-kpi" />)}
        </div>
        <div className="db-skeleton-grid" style={{ marginTop: 16 }}>
          {[1,2,3,4].map(n => <div key={n} className="db-skeleton-chart" />)}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
          <div style={{ fontSize: '.85rem', color: '#991B1B' }}>
            Kon geen data ophalen voor <strong>{instelling}</strong>. {error}
          </div>
        </div>
      </div>
    )
  }

  if (!data.gevonden) {
    const suggesties = data.beschikbare_instellingen || []
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
          <div style={{ fontSize: '.85rem', color: '#92400E', lineHeight: 1.6 }}>
            <strong>&ldquo;{instelling}&rdquo;</strong> niet gevonden in DUO-data.
            {suggesties.length > 0 && (
              <> Bedoel je misschien: {suggesties.slice(0,5).join(', ')}?</>
            )}
            <br />Pas de naam aan via <strong>Instellingen</strong>.
          </div>
        </div>
      </div>
    )
  }

  return children
}

export function Sparkline({ values, color = '#2563EB', width = 80, height = 28 }) {
  const pts = values.filter(v => v != null)
  if (pts.length < 2) return null
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  const range = max - min || 1
  const step = width / (pts.length - 1)
  const points = pts.map((v, i) => {
    const x = i * step
    const y = height - ((v - min) / range) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={width} height={height} style={{ display: 'block', marginTop: 4 }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function SectionHeader({ title, subtitle }) {
  return (
    <div style={{ margin: '28px 0 12px', borderBottom: '1px solid var(--gray-200)', paddingBottom: 8 }}>
      <h3 style={{ fontWeight: 700, fontSize: '.95rem', color: 'var(--gray-900)', margin: 0 }}>{title}</h3>
      {subtitle && <div style={{ fontSize: '.8rem', color: 'var(--gray-500)', marginTop: 2 }}>{subtitle}</div>}
    </div>
  )
}

export function ChartCard({ title, subtitle, children, cardStyle, actions }) {
  return (
    <div className="charts-grid charts-grid-single">
      <div className="chart-card" style={cardStyle} aria-label={title || undefined}>
        {(title || subtitle || actions) && (
          <div className="chart-header" style={actions ? { display: 'flex', alignItems: 'flex-start' } : undefined}>
            <div>
              {title && <div className="chart-title">{title}</div>}
              {subtitle && <div className="chart-sub">{subtitle}</div>}
            </div>
            {actions}
          </div>
        )}
        {children}
      </div>
    </div>
  )
}

export function RegioBadges({ instelling, provincie, arbeidsmarktregio, bron }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
      <span className="meta-badge instelling">{instelling}</span>
      {arbeidsmarktregio && <span className="meta-badge date">Regio {arbeidsmarktregio}</span>}
      {provincie && <span className="meta-badge date">Provincie {provincie}</span>}
      <span className="meta-badge date">Bron: {bron}</span>
    </div>
  )
}

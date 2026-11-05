import { COLOR_EIGEN, COLOR_DIPLOM, COLOR_EERSTEJAARS } from '../../../constants'
import { jaarLabel } from '../../../schooljaar'
import { SectionHeader, fmt, Sparkline, JaarNoot, eerstejaarsNoot, gediplomeerdenNoot, sortedEntries, perJaar, isOndergrens, TenMinste } from '../shared/index'

// De kerncijfers bovenaan "Mijn instelling": de eigen instelling tegenover het gemiddelde van het benchmark. Een eigen
// component, omdat de galerijkaart dezelfde rij toont als miniatuur van het dashboard (#933).

function SamenvattingTile({ label, eigenWaarde, regioWaarde, regioLabel, sparkValues, color, icon, suffix, ondergrens, regioOndergrens, noot, nootId }) {
  return (
    <div className="kpi-card">
      <div className="kpi-card-header">
        <span className="kpi-label">{label}</span>
        <div className="kpi-icon" style={{ background: `${color}18` }}>{icon}</div>
      </div>
      <div className="kpi-value"><TenMinste actief={ondergrens} />{fmt(eigenWaarde)}{suffix}</div>
      {regioWaarde != null && (
        <div className="kpi-trend" style={{ color: 'var(--gray-500)' }}>
          {regioLabel}: {regioOndergrens ? 'ten minste ' : ''}{fmt(regioWaarde)}
        </div>
      )}
      <JaarNoot noot={noot} testid={nootId} />
      {sparkValues && <Sparkline values={sparkValues} color={color} />}
    </div>
  )
}

const iconPersons = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
)
const iconChart = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
)
const iconDiploma = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
)
const iconGender = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
)

// `c`: useRegioComputed van dezelfde payload.
export function Kerncijfers({ data, instelling, c }) {
  const bm = c.bm || {}
  const { perioden } = c
  // Onderdrukte cellen per reeks en jaar (#902): een getal daarover is "ten minste".
  const od = data?.onderdrukt || {}
  const bmOd = bm.onderdrukt || {}
  const bmLaatste = sleutel => sortedEntries(bm[sleutel]).at(-1) ?? [null, null]
  const [bmIngesJaar, bmInges] = bmLaatste('ingeschrevenen')
  const [bmEjJaar, bmEj] = bmLaatste('eerstejaars')
  const [bmDiplJaar, bmDipl] = bmLaatste('gediplomeerden')
  // Het aantal peers achter het gemiddelde van dat jaar (#903): niet elke peer heeft elk jaar data.
  const gemLabel = (sleutel, jaar) => {
    const n = perJaar(bm.n_per_jaar?.[sleutel], jaar)
    return `Gem. ${bm.populatie || 'vergelijkingsgroep'}${n != null ? ` (${n} instellingen)` : ''}`
  }

  // De kop noemt de vergelijkingsgroep met regio, aantal, type en een eventuele terugval met reden (#926).
  return (
    <>
      <SectionHeader title="Kerncijfers" subtitle={bm.label ? `${instelling} vs. ${bm.label}` : `${instelling} — in één oogopslag`} />
      <div className="kpi-grid">
        {c.lastInges && (
          <SamenvattingTile
            label={`Ingeschrevenen ${jaarLabel(c.lastInges[0], perioden?.ingeschrevenen)}`}
            eigenWaarde={c.lastInges[1]}
            regioWaarde={bmInges ? Math.round(bmInges) : null}
            regioLabel={gemLabel('ingeschrevenen', bmIngesJaar)}
            sparkValues={c.ingesEntries.map(([, v]) => v)}
            color={COLOR_EIGEN}
            icon={iconPersons(COLOR_EIGEN)}
            ondergrens={isOndergrens(od.ingeschrevenen, c.lastInges[0])}
            regioOndergrens={isOndergrens(bmOd.ingeschrevenen, bmIngesJaar)}
          />
        )}
        {c.lastEj && (
          <SamenvattingTile
            label={`Eerstejaars ${jaarLabel(c.lastEj[0], perioden?.eerstejaars)}`}
            eigenWaarde={c.lastEj[1]}
            regioWaarde={bmEj ? Math.round(bmEj) : null}
            regioLabel={gemLabel('eerstejaars', bmEjJaar)}
            sparkValues={c.ejEntries.map(([, v]) => v)}
            color={COLOR_EERSTEJAARS}
            icon={iconChart(COLOR_EERSTEJAARS)}
            ondergrens={isOndergrens(od.eerstejaars, c.lastEj[0])}
            regioOndergrens={isOndergrens(bmOd.eerstejaars, bmEjJaar)}
            noot={eerstejaarsNoot({ ejJaar: c.lastEj[0], ingesJaar: c.lastInges?.[0], type: data?.type, perioden })}
          />
        )}
        {c.lastDipl && (
          <SamenvattingTile
            label={`Gediplomeerden ${jaarLabel(c.lastDipl[0], perioden?.gediplomeerden)}`}
            eigenWaarde={c.lastDipl[1]}
            regioWaarde={bmDipl ? Math.round(bmDipl) : null}
            regioLabel={gemLabel('gediplomeerden', bmDiplJaar)}
            sparkValues={c.diplEntries.map(([, v]) => v)}
            color={COLOR_DIPLOM}
            icon={iconDiploma(COLOR_DIPLOM)}
            ondergrens={isOndergrens(od.gediplomeerden, c.lastDipl[0])}
            regioOndergrens={isOndergrens(bmOd.gediplomeerden, bmDiplJaar)}
            noot={gediplomeerdenNoot({ diplJaar: c.lastDipl[0], ingesJaar: c.lastInges?.[0], perioden })}
            nootId="diplomanoot"
          />
        )}
        {c.pctVrouw != null && (
          <SamenvattingTile
            label={`Aandeel vrouw ${jaarLabel(data?.laatste_jaar, perioden?.ingeschrevenen)}`}
            eigenWaarde={c.pctVrouw}
            suffix="%"
            regioWaarde={null}
            regioLabel=""
            color="#F59E0B"
            icon={iconGender('#F59E0B')}
          />
        )}
      </div>
    </>
  )
}

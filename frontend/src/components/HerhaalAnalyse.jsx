import { useId, useState } from 'react'
import { herhaalAnalyse } from '../api'
import { useGeavanceerd } from '../geavanceerd'
import {
  HERHAAL_BEZIG, HERHAAL_KNOP, HERHAAL_KOP, HERHAAL_NOOT, REDEN_ZONDER_HASH, STATUS, kanHashen, standTekst, toontHerhaal,
} from '../herhaalAnalyse'

// "Herhaal deze analyse" (#1240) onder een data-antwoord met een CBS-tabel, achter "Geavanceerd" (#1269): het voegt
// iets toe en vervangt niets. De uitkomst staat als tak onder het antwoord, per tabel de stand van nu naast die van
// toen; het antwoord zelf verandert niet en de herhaling wordt niet bewaard (herhaalAnalyse.js).
function Tabel({ tabel }) {
  const tekst = tabel.status === 'mislukt' ? tabel.melding : tabel.samenvatting
  return (
    <li className="herhaal-tabel" data-status={tabel.status}>
      <p className="herhaal-tabel-kop">
        <span className="herhaal-status">{STATUS[tabel.status] || tabel.status}</span>
        {' '}
        <span className="herhaal-titel">{tabel.titel}{tabel.dataset && tabel.titel !== tabel.dataset ? ` (${tabel.dataset})` : ''}</span>
      </p>
      {tekst && <p className="herhaal-zin">{tekst}</p>}
      {(tabel.toen || tabel.nu) && (
        <dl className="herhaal-stand">
          {tabel.toen && <div><dt>Toen</dt><dd>{standTekst(tabel.toen)}</dd></div>}
          {tabel.nu && <div><dt>Nu</dt><dd>{standTekst(tabel.nu)}</dd></div>}
        </dl>
      )}
    </li>
  )
}

export function HerhaalUitkomst({ uitkomst }) {
  const tabellen = Array.isArray(uitkomst?.tabellen) ? uitkomst.tabellen : []
  const overgeslagen = Array.isArray(uitkomst?.overgeslagen) ? uitkomst.overgeslagen : []
  return (
    <div className="herhaal-uitkomst">
      <p className="herhaal-kop">{HERHAAL_KOP}</p>
      {uitkomst?.melding && <p className="herhaal-zin">{uitkomst.melding}</p>}
      {tabellen.length > 0 && (
        <ul className="herhaal-tabellen">
          {tabellen.map((t, i) => <Tabel key={`${t.dataset}-${i}`} tabel={t} />)}
        </ul>
      )}
      {overgeslagen.map(zin => <p key={zin} className="herhaal-overgeslagen">{zin}</p>)}
      <p className="herhaal-noot">{HERHAAL_NOOT}</p>
    </div>
  )
}

// `herhaal` en `hashbaar` zijn er voor de tests: de API-aanroep en of de browser de sleutel kan maken.
export default function HerhaalAnalyse({ msg, gesprekId, herhaal = herhaalAnalyse, hashbaar = kanHashen() }) {
  const geavanceerd = useGeavanceerd()
  const [bezig, setBezig] = useState(false)
  const [uitkomst, setUitkomst] = useState(null)
  const [fout, setFout] = useState(null)
  const redenId = useId()
  if (!geavanceerd || !gesprekId || !toontHerhaal(msg)) return null

  async function start() {
    setBezig(true)
    setFout(null)
    try {
      setUitkomst(await herhaal(gesprekId, msg.content))
    } catch (e) {
      setFout(e?.message || 'Herhalen lukte nu niet. Probeer het later opnieuw.')
    } finally {
      setBezig(false)
    }
  }

  return (
    <div className="herhaal-analyse">
      <button
        type="button" className="message-continue" onClick={start} disabled={bezig || !hashbaar}
        aria-describedby={hashbaar ? undefined : redenId}
      >
        {HERHAAL_KNOP}
      </button>
      {!hashbaar && <span id={redenId} className="herhaal-reden">{REDEN_ZONDER_HASH}</span>}
      <div role="status" aria-live="polite" className="herhaal-wacht">{bezig ? HERHAAL_BEZIG : ''}</div>
      {fout && <p className="herhaal-melding" role="alert">{fout}</p>}
      {uitkomst && !bezig && <HerhaalUitkomst uitkomst={uitkomst} />}
    </div>
  )
}

import { stukken, WACHT_LABEL, WACHT_TEKEN } from '../getalWacht'

// Platte tekst waarin elk getal dat nog op de controle wacht een "…" is (#1254), zoals rehypeGetalWacht in markdown.
export default function WachtTekst({ tekst, regel }) {
  return stukken(tekst || '', regel).map((stuk, i) => (stuk.wacht
    ? <span key={i} className="getal-wacht" role="img" aria-label={WACHT_LABEL} aria-busy="true" style={{ width: `${stuk.wacht}ch` }}>{WACHT_TEKEN}</span>
    : stuk.tekst))
}

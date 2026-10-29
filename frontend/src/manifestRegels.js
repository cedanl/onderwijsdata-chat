// Herkomst van een antwoord of rapport (#345) als twee leesregels: wat het maakte en welke dataversie erachter zit.
// Eén bron voor het rapport (reportHtml.js) en de gespreksexport (conversationExport.js, #713).
const zonderProvider = id => String(id).split('/').pop()
const modelNaam = m => m.model_naam || zonderProvider(m.model)
const toegepast = v => (v === true ? 'toegepast' : v === false ? 'niet toegepast' : 'onbekend')

// `null` zonder manifest of zonder model: dan valt er niets te verantwoorden.
export function manifestRegels(manifest) {
  if (!manifest || !manifest.model) return null
  const m = manifest
  const verantwoording = [
    `model ${modelNaam(m)}${m.model_versie ? ` (${zonderProvider(m.model_versie)})` : ''}`,
    m.sampling ? `seed ${toegepast(m.sampling.seed_toegepast)}` : '',
    m.prompt_hash ? `prompt ${m.prompt_hash}` : '',
    m.catalogus ? `catalogus ${m.catalogus}` : '',
    m.app ? `app ${m.app}` : '',
  ].filter(Boolean).join(' · ')
  const dataversie = (m.data_as_of || []).map(d => {
    const extra = [
      d.laatste_update ? `bijgewerkt ${d.laatste_update}` : '',
      d.periodestatus?.length ? `status ${d.periodestatus.join('/')}` : '',
      d.herladen_op ? `herladen ${d.herladen_op}` : '',
      d.peilmoment || '',
    ].filter(Boolean).join(', ')
    return `${d.bron.toUpperCase()} ${d.dataset}${extra ? ` (${extra})` : ''}`
  }).join(' · ')
  return { verantwoording, dataversie }
}

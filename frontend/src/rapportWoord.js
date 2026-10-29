import { getWorkbookType } from './workbooks'

// Een rapport en een dashboard delen de viewer en de feedbackvragen (#795). De teksten zeggen "rapport"; voor een
// dashboard zetten we het woord om. Beide zijn het-woorden, dus "dit", "het" en "over het" blijven kloppen.
export const rapportWoord = workbook => (getWorkbookType(workbook) === 'dashboard' ? 'dashboard' : 'rapport')

export const metWoord = (tekst, woord) =>
  woord === 'rapport' ? tekst : tekst.replace(/rapport(en)?/g, (_, meervoud) => (meervoud ? `${woord}s` : woord))

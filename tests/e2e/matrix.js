/**
 * Slagingspercentage per model en per vraag over herhaalde beurten (#190). Puur, zodat
 * score-unit.mjs het zonder app en zonder LLM toetst.
 *
 * Eén geslaagde beurt zegt weinig (het RIO-verschil tussen audit 7a en 7b): elke vraag draait
 * TEST_REPEATS keer per model, en een fout in één van de beurten telt. De matrix gaat als JSON
 * naar eval_results/, naast de losse logs.
 */

export function nieuweMatrix() {
  return {}
}

/** Eén beurt erbij: model × label → { beurten, geslaagd }. */
export function voegToe(matrix, model, label, geslaagd) {
  const perModel = (matrix[model] ??= {})
  const cel = (perModel[label] ??= { beurten: 0, geslaagd: 0 })
  cel.beurten += 1
  if (geslaagd) cel.geslaagd += 1
  return matrix
}

/** Per model en vraag het percentage geslaagde beurten, plus het gemiddelde per model. */
export function slagingspercentages(matrix) {
  const uit = {}
  for (const [model, vragen] of Object.entries(matrix)) {
    const perVraag = {}
    let beurten = 0, geslaagd = 0
    for (const [label, cel] of Object.entries(vragen)) {
      perVraag[label] = { ...cel, percentage: cel.beurten ? Math.round(100 * cel.geslaagd / cel.beurten) : null }
      beurten += cel.beurten
      geslaagd += cel.geslaagd
    }
    uit[model] = { vragen: perVraag, beurten, geslaagd, percentage: beurten ? Math.round(100 * geslaagd / beurten) : null }
  }
  return uit
}

export function rapport(matrix, { gemeten_op = new Date().toISOString().slice(0, 10), herhalingen = 1 } = {}) {
  return { gemeten_op, herhalingen, modellen: slagingspercentages(matrix) }
}

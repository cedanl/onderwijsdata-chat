// Na alle workers (#753): de verslagen uit eval_results/runs.jsonl, en per model de regel van de kritieke set.
import { readFileSync } from 'node:fs'
import { schrijfVerslagen } from './runlog.js'

const EVALS = JSON.parse(readFileSync(new URL('./evaluations.json', import.meta.url), 'utf-8')).evaluations

export default function () {
  const herhalingen = Math.max(1, Number(process.env.TEST_REPEATS) || 1)
  for (const regel of schrijfVerslagen(EVALS, { herhalingen })) console.log(regel)
}

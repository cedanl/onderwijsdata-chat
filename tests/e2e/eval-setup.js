// Vóór een eval-run (#753): de runs van een vorige run tellen niet mee in de verslagen van deze.
import { wisRuns } from './runlog.js'

export default function () {
  wisRuns()
}

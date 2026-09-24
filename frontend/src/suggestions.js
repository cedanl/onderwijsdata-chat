// Suggested questions are written in the first person ("ons", "mijn regio"); with an
// institution in the profile they name it instead.
export function personalizeQuestion(q, instelling) {
  if (!instelling) return q
  return q
    .replaceAll('ons onderwijsaanbod', `het aanbod van ${instelling}`)
    .replaceAll('onze instelling', instelling)
    .replaceAll('mijn lerenden', `de lerenden van ${instelling}`)
    .replaceAll('mijn regio', `de regio van ${instelling}`)
    .replaceAll('bij ons', `bij ${instelling}`)
}

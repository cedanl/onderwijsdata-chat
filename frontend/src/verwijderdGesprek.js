// Het open gesprek dat de gebruiker verwijderde (#530, privacy M7). Het blijft op het scherm staan,
// maar mag niet terug in localStorage: niet bij een afgerond antwoord, niet bij pagehide. Pas een
// nieuwe vraag in dat scherm maakt er weer een gesprek van dat bewaard mag worden.
const aantalVragen = messages => messages.filter(m => m.role === 'user').length

// De markering bij het bevestigen van de verwijdering.
export function markeerVerwijderd(id, messages) {
  return { id: String(id), vragen: aantalVragen(messages) }
}

// Waar als `messages` van gesprek `id` nog het verwijderde gesprek zijn: zelfde id, geen nieuwe vraag.
// Een antwoord dat na het verwijderen nog binnenkomt (of in de deltabuffer zit) telt niet als nieuw.
export function isVerwijderd(markering, id, messages) {
  return Boolean(markering) && markering.id === String(id) && aantalVragen(messages) === markering.vragen
}

// The profile the whole app works with (#777): the kop, the chat, the dashboards and the reports read the same one.

// The instelling: the user's own choice from Instellingen, and as long as there is none, the known instelling their SRAM
// account gives. A choice wins even when it is empty: whoever clears the instelling and saves chose to have none.
export function effectieveInstelling(settings, sramInstelling) {
  return settings.instelling ?? sramInstelling ?? ''
}

// The saved settings with that instelling in place.
export function effectiefProfiel(settings, sramInstelling) {
  return { ...settings, instelling: effectieveInstelling(settings, sramInstelling) }
}

// No profile yet: no instelling (neither chosen nor from SRAM) and no functie. The onboarding opens on that,
// whichever way the user logged in; a recognised SRAM instelling therefore counts as a profile.
export function zonderProfiel(profiel) {
  return !profiel.instelling?.trim() && !profiel.functie
}

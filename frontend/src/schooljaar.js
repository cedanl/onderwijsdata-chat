// Een schooljaar zoals chat en rapport het schrijven (tools/periode.label): startjaar 2024 is "2024/25" (#920).
export function schooljaarLabel(startjaar) {
  const start = Number(startjaar)
  return `${start}/${String((start + 1) % 100).padStart(2, '0')}`
}

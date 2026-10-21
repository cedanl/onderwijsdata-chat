// "Vandaag", "Gisteren" or a short date in a list; with the time, two conversations of one day can be told apart
// (#654). Local `new Date(y, m, d, h, min)` timestamps, so the tests do not depend on the time zone.
import { describe, it, expect } from 'vitest'
import { relatieveDatum, relatieveDatumTijd } from '../relatieveDatum'

const NU = new Date(2026, 9, 21, 10, 0).getTime()
const ms = (d, h, min) => new Date(2026, 9, d, h, min).getTime()

describe('relatieveDatum', () => {
  it('counts calendar days, not 24-hour blocks', () => {
    expect(relatieveDatum(ms(21, 0, 5), NU)).toBe('Vandaag')
    // Last night at 23:50 is yesterday, even though it is less than 24 hours ago.
    expect(relatieveDatum(ms(20, 23, 50), NU)).toBe('Gisteren')
    expect(relatieveDatum(ms(20, 0, 5), NU)).toBe('Gisteren')
    expect(relatieveDatum(ms(19, 23, 50), NU)).toBe('19 okt')
  })

  it('reads seconds from the server and milliseconds from the browser', () => {
    expect(relatieveDatum(ms(20, 9, 0) / 1000, NU)).toBe('Gisteren')
    expect(relatieveDatum(ms(12, 9, 0), NU)).toBe('12 okt')
  })
})

describe('relatieveDatumTijd', () => {
  it('adds the local time as HH:MM', () => {
    expect(relatieveDatumTijd(ms(21, 9, 5), NU)).toBe('Vandaag 09:05')
    expect(relatieveDatumTijd(ms(20, 23, 50), NU)).toBe('Gisteren 23:50')
    expect(relatieveDatumTijd(ms(12, 14, 32) / 1000, NU)).toBe('12 okt 14:32')
  })

  it('tells two conversations of the same day apart', () => {
    const eerste = relatieveDatumTijd(ms(21, 9, 0), NU)
    const tweede = relatieveDatumTijd(ms(21, 9, 10), NU)
    expect(eerste).not.toBe(tweede)
    expect([eerste, tweede]).toEqual(['Vandaag 09:00', 'Vandaag 09:10'])
  })
})

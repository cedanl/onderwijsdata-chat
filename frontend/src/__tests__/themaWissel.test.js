// @vitest-environment jsdom
// #834: één useDarkMode voor de hele app. Het gegenereerde dashboard dat hier ook een themawissel volgde, is weg
// met de dashboardbouwer (#765).
import { describe, it, expect } from 'vitest'

import { useDarkMode as appHook } from '../hooks/useDarkMode'
import { useDarkMode as dashboardHook } from '../components/dashboards/shared'

describe('themawissel (#834)', () => {
  it('de dashboards gebruiken dezelfde useDarkMode als de rest van de app', () => {
    expect(dashboardHook).toBe(appHook)
  })
})

import { describe, it, expect } from 'vitest'

describe('DashboardSpec structure', () => {
  const validSpec = {
    title: 'Test Dashboard',
    description: 'Een test dashboard',
    narrative: '## Samenvatting\nDit is een test.',
    kpis: [
      { label: 'Studenten', value: '1.234', trend: '+5%', trendDirection: 'up', sub: 't.o.v. vorig jaar' },
      { label: 'Gediplomeerden', value: '890', sub: 'in 2024' },
    ],
    figures_json: [
      JSON.stringify({
        data: [{ x: [2020, 2021], y: [100, 200], type: 'bar' }],
        layout: { title: { text: 'Instroom' } },
      }),
    ],
    sources: ['DUO — p01hoinges', 'CBS — 85423NED'],
    recipe: [{ name: 'get_duo_data', arguments: '{"dataset_id": "p01hoinges"}' }],
  }

  it('has all required fields', () => {
    expect(validSpec).toHaveProperty('title')
    expect(validSpec).toHaveProperty('kpis')
    expect(validSpec).toHaveProperty('figures_json')
    expect(validSpec).toHaveProperty('sources')
    expect(validSpec).toHaveProperty('recipe')
    expect(validSpec).toHaveProperty('narrative')
  })

  it('kpis have correct structure', () => {
    for (const kpi of validSpec.kpis) {
      expect(kpi).toHaveProperty('label')
      expect(kpi).toHaveProperty('value')
    }
  })

  it('figures_json contains valid JSON strings', () => {
    for (const fig of validSpec.figures_json) {
      const parsed = JSON.parse(fig)
      expect(parsed).toHaveProperty('data')
      expect(parsed).toHaveProperty('layout')
    }
  })

  it('recipe contains valid tool calls', () => {
    for (const tc of validSpec.recipe) {
      expect(tc).toHaveProperty('name')
      expect(tc).toHaveProperty('arguments')
    }
  })

  it('handles empty spec gracefully', () => {
    const emptySpec = { title: 'Leeg' }
    expect(emptySpec.kpis ?? []).toEqual([])
    expect(emptySpec.figures_json ?? []).toEqual([])
    expect(emptySpec.sources ?? []).toEqual([])
    expect(emptySpec.recipe ?? []).toEqual([])
    expect(emptySpec.narrative ?? '').toBe('')
  })
})

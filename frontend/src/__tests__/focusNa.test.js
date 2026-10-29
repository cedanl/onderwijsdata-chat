// @vitest-environment jsdom
// #776: waar de focus heen gaat als het gefocuste element verdwijnt.
import { describe, it, expect, afterEach } from 'vitest'
import { buurVan, kiezerMetId, focusEerste, idsInDocument } from '../focusNa'

afterEach(() => { document.body.innerHTML = '' })

describe('buurVan', () => {
  it('kiest het volgende item, aan het eind het vorige, en null als er niets overblijft', () => {
    expect(buurVan(['a', 'b', 'c'], 'b')).toBe('c')
    expect(buurVan(['a', 'b', 'c'], 'c')).toBe('b')
    expect(buurVan(['a'], 'a')).toBeNull()
    expect(buurVan(['a', 'b'], 'x')).toBeNull()
  })

  it('vergelijkt als tekst: een id uit een data-attribuut is altijd een string', () => {
    expect(buurVan(['1', '2'], 1)).toBe('2')
  })
})

describe('kiezerMetId', () => {
  it('maakt een attribuutkiezer die ook met aanhalingstekens in de id klopt', () => {
    document.body.innerHTML = '<button data-conv-id=\'a"b\\c\'>x</button>'
    expect(document.querySelector(kiezerMetId('button', 'data-conv-id', 'a"b\\c'))).not.toBeNull()
  })
})

describe('idsInDocument', () => {
  it('geeft de ids in documentvolgorde', () => {
    document.body.innerHTML = '<i data-x="2"></i><b data-x="1"></b><i></i>'
    expect(idsInDocument('[data-x]', 'data-x')).toEqual(['2', '1'])
  })
})

describe('focusEerste', () => {
  it('zet de focus op het eerste element dat bestaat en hem aanneemt', () => {
    document.body.innerHTML = '<button id="uit" disabled>a</button><div id="niet">b</div><button id="ja">c</button>'
    expect(focusEerste('#weg', '#uit', '#niet', '#ja')).toBe(true)
    expect(document.activeElement.id).toBe('ja')
  })

  it('slaat lege kiezers over en zegt het als niets de focus aannam', () => {
    document.body.innerHTML = '<span>a</span>'
    expect(focusEerste(null, '', '#weg', 'span')).toBe(false)
  })
})

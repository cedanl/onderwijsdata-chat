import { STORAGE_TOKEN } from './constants'

const KEY = STORAGE_TOKEN

export const getToken = () => localStorage.getItem(KEY)
export const setToken = (t) => localStorage.setItem(KEY, t)
export const clearToken = () => localStorage.removeItem(KEY)

export async function fetchAuthStatus() {
  const res = await fetch("/api/auth/status")
  return res.json()
}

export async function login(username, password) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || "Inloggen mislukt")
  }
  const data = await res.json()
  setToken(data.token)
  return data
}

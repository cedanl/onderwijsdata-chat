import { STORAGE_TOKEN } from './constants'

export const getToken = () => localStorage.getItem(STORAGE_TOKEN)
export const setToken = (t) => localStorage.setItem(STORAGE_TOKEN, t)
export const clearToken = () => localStorage.removeItem(STORAGE_TOKEN)

export async function fetchAuthStatus() {
  const res = await fetch("/api/auth/status")
  if (!res.ok) throw new Error(`Auth status check failed: ${res.status}`)
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

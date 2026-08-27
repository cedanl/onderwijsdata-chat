import { STORAGE_TOKEN } from './constants'

export const getToken = () => localStorage.getItem(STORAGE_TOKEN)
const setToken = (t) => localStorage.setItem(STORAGE_TOKEN, t)
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

// After a redirect back from /api/auth/oidc/callback, the token arrives as
// ?token=... on the URL. Pick it up, persist it, and strip it from the URL
// (it shouldn't linger in browser history).
export function consumeTokenFromUrl() {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')
  if (!token) return null
  setToken(token)
  
  // Also extract user_data if present (from SRAM OIDC callback)
  const userDataParam = params.get('user_data')
  let userData = null
  if (userDataParam) {
    try {
      userData = JSON.parse(decodeURIComponent(userDataParam))
    } catch {
      // Ignore parse errors
    }
  }
  
  params.delete('token')
  params.delete('user_data')
  const query = params.toString()
  window.history.replaceState({}, '', window.location.pathname + (query ? `?${query}` : ''))
  
  return { token, userData }
}

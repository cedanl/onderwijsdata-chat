import { STORAGE_TOKEN } from './constants'

const STORAGE_USERINFO = 'userInfo'

export const getToken = () => localStorage.getItem(STORAGE_TOKEN)
const setToken = (t) => localStorage.setItem(STORAGE_TOKEN, t)
export const clearToken = () => {
  localStorage.removeItem(STORAGE_TOKEN)
  localStorage.removeItem(STORAGE_USERINFO)
}

export const getUserInfo = () => {
  const item = localStorage.getItem(STORAGE_USERINFO)
  if (!item) return null
  try {
    return JSON.parse(item)
  } catch {
    return null
  }
}

const setUserInfo = (info) => localStorage.setItem(STORAGE_USERINFO, JSON.stringify(info))

export async function fetchAuthStatus() {
  const res = await fetch("/api/auth/status")
  if (!res.ok) throw new Error(`Auth status check failed: ${res.status}`)
  return res.json()
}

// Fetch user info from server (OIDC only, server is source of truth)
// GitHub version (basic auth) doesn't have this endpoint
export async function fetchUserInfo(token) {
  try {
    const res = await fetch(`/api/auth/user?token=${encodeURIComponent(token)}`)
    if (res.status === 404) return null  // Endpoint doesn't exist (GitHub version)
    if (!res.ok) {
      if (res.status === 401) return null
      throw new Error(`User info fetch failed: ${res.status}`)
    }
    return res.json()
  } catch (err) {
    console.warn('fetchUserInfo failed (expected on GitHub/basic-auth version):', err)
    return null
  }
}

// Refresh auth token before expiration (OIDC only)
// GitHub version (basic auth) doesn't support this
export async function refreshAuthToken(token) {
  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
    if (res.status === 404) return null  // Endpoint doesn't exist (GitHub version)
    if (!res.ok) {
      if (res.status === 401) return null
      throw new Error(`Token refresh failed: ${res.status}`)
    }
    const { token: newToken, user } = await res.json()
    setToken(newToken)
    if (user) setUserInfo(user)
    return { newToken, user }
  } catch (err) {
    console.warn('refreshAuthToken failed (expected on GitHub/basic-auth version):', err)
    return null
  }
}

// Retrieve stored SRAM user info (fallback, prefer fetchUserInfo for fresh data)
export function getStoredUserInfo() {
  return getUserInfo()
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

  // Extract user_data if present (from SRAM OIDC callback) and persist it
  const userDataParam = params.get('user_data')
  let userData = null
  if (userDataParam) {
    try {
      userData = JSON.parse(decodeURIComponent(userDataParam))
      setUserInfo(userData)
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

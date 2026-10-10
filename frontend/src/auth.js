import { STORAGE_TOKEN } from './constants'

const STORAGE_USERINFO = 'userInfo'

export const getToken = () => localStorage.getItem(STORAGE_TOKEN)
const setToken = (t) => localStorage.setItem(STORAGE_TOKEN, t)
export const clearToken = () => {
  localStorage.removeItem(STORAGE_TOKEN)
  localStorage.removeItem(STORAGE_USERINFO)
}

const sessionEndedListeners = new Set()

// The server no longer accepts the token (expired or tampered): drop it and let the app
// show the login screen (#480). Logout clears the token itself; it needs no notice.
export function endSession() {
  clearToken()
  sessionEndedListeners.forEach(cb => cb())
}

export function onSessionEnded(cb) {
  sessionEndedListeners.add(cb)
  return () => { sessionEndedListeners.delete(cb) }
}

// A 401 for an older token (a parallel request, or one from before a new login) has no
// session left to end.
export function endSessionIfCurrent(token) {
  if (token && token === getToken()) endSession()
}

// True when there was a session at some earlier point and it has since been
// cleared (logout or expiry). With auth off there is never a token: false.
export const sessionEndedSince = (tokenThen) => tokenThen !== null && getToken() === null

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
    const res = await fetch('/api/auth/user', { headers: { Authorization: `Bearer ${token}` } })
    if (res.status === 401) {
      endSessionIfCurrent(token)
      return null
    }
    if (res.status === 404) return null  // Endpoint doesn't exist (GitHub version)
    if (!res.ok) throw new Error(`User info fetch failed: ${res.status}`)
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
    if (res.status === 401) {
      endSessionIfCurrent(token)
      return null
    }
    if (res.status === 404) return null  // Endpoint doesn't exist (GitHub version)
    if (!res.ok) throw new Error(`Token refresh failed: ${res.status}`)
    const { token: newToken, user } = await res.json()
    setToken(newToken)
    if (user) setUserInfo(user)
    return { newToken, user }
  } catch (err) {
    console.warn('refreshAuthToken failed (expected on GitHub/basic-auth version):', err)
    return null
  }
}

// A refused WebSocket handshake reaches the browser as a bare close 1006, the same as a
// network outage. Ask the server: only an explicit 401 ends the session (#480).
export async function checkSession() {
  const token = getToken()
  if (!token) return
  try {
    const res = await fetch('/api/auth/user', { headers: { Authorization: `Bearer ${token}` } })
    if (res.status === 401) endSessionIfCurrent(token)
  } catch {
    // Offline: the socket keeps retrying, the token stays.
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

// Revoke the token server-side (#479). Fire-and-forget: logging out locally never waits for it or fails on it.
export function logout(token) {
  if (!token) return
  fetch('/api/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => {})
}

// Tokens are `base64url("<username>|<session start>|<expiry seconds>").<signature>` (older: no start); returns the expiry in ms.
export function tokenExpiresAt(token) {
  try {
    const decoded = atob(token.split('.')[0].replace(/-/g, '+').replace(/_/g, '/'))
    const seconds = Number(decoded.slice(decoded.lastIndexOf('|') + 1))
    return seconds > 0 ? seconds * 1000 : null
  } catch {
    return null
  }
}

// The chat socket carries the token as subprotocol ["bearer", token]: a browser
// cannot set headers on a WebSocket, and a query string ends up in logs (#103).
export function chatSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  return new WebSocket(`${proto}://${location.host}/api/chat`, token ? ['bearer', token] : undefined)
}

// After a redirect back from /api/auth/oidc/callback, the token arrives in the
// fragment (#token=...), which a browser never sends to a server or proxy (#103).
// Pick it up, persist it, and strip it from the URL (it shouldn't linger in history).
export function consumeTokenFromUrl() {
  const params = new URLSearchParams(window.location.hash.slice(1))
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
  const rest = params.toString()
  window.history.replaceState({}, '', window.location.pathname + window.location.search + (rest ? `#${rest}` : ''))

  return { token, userData }
}

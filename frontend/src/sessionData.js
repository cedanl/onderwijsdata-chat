import { SESSION_DATA_KEYS } from './constants'

// Conversations, workbooks and the dashboard chat cached by whoever used this browser before.
// The pages that sync them to the server cannot tell leftovers from unsynced data, and would
// attribute them to the account that logs in next.
export function clearLocalSessionData() {
  for (const key of SESSION_DATA_KEYS) localStorage.removeItem(key)
}

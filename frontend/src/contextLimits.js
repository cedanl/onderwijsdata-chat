import { MAX_CHAT_TURNS, MAX_HISTORY } from './constants'

// From this share of the question limit the chat warns that it is getting full (16 of 20).
const WARN_FROM = 0.8

// A limit from /api/config if it is a positive integer, otherwise the fallback constant (#501, #789).
export function resolveLimit(value, fallback) {
  return Number.isInteger(value) && value > 0 ? value : fallback
}

export const resolveMaxChatTurns = value => resolveLimit(value, MAX_CHAT_TURNS)
export const resolveMaxHistory = value => resolveLimit(value, MAX_HISTORY)

export function warnChatTurns(maxChatTurns) {
  return Math.ceil(maxChatTurns * WARN_FROM)
}

// At most `max` messages, the first question always in front (#789): the same cut as the server's
// agent/history.py trim, so a reopened conversation keeps its subject like the live one. The client history
// holds only questions and answers, so trim's dropping of orphaned tool messages has nothing to do here.
export function trimHistory(history, max = MAX_HISTORY) {
  if (history.length <= max) return history
  const firstUser = history.find(m => m.role === 'user')
  const tail = history.slice(-(max - 1))
  return firstUser && !tail.includes(firstUser) ? [firstUser, ...tail] : tail
}

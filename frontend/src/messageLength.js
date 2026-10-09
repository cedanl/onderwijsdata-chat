import { MAX_MESSAGE_CHARS } from './constants'

// From this share of the maximum the composer shows its character counter.
const COUNTER_FROM = 0.8

// Where a draft stands against the message limit (#481). Counted like the server: after trim().
// JS counts UTF-16 units and Python code points, so the composer is never more lenient.
export function messageLengthState(text, max = MAX_MESSAGE_CHARS) {
  const count = text.trim().length
  return {
    count,
    max,
    atLimit: count >= max,
    over: count > max,
    showCounter: count >= Math.ceil(max * COUNTER_FROM),
  }
}

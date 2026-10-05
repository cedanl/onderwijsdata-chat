import { useCallback, useEffect, useState } from 'react'
import { fetchAnswerFeedback, postAnswerFeedback } from '../api'

// The judgement per answer in the open conversation (#248), keyed by message index.
// The server takes the trace from the stored conversation, so `save` runs first:
// a just-finished answer must be on the server before it can be judged.
export function useAnswerFeedback({ conversationId, enabled, save }) {
  const [oordelen, setOordelen] = useState({})

  useEffect(() => {
    setOordelen({})
    if (!enabled || !conversationId) return
    let cancelled = false
    fetchAnswerFeedback(String(conversationId))
      .then(map => { if (!cancelled) setOordelen(map) })
      .catch(() => { /* the buttons still work; only the earlier state is missing */ })
    return () => { cancelled = true }
  }, [conversationId, enabled])

  const submit = useCallback(async (index, oordeel, toelichting) => {
    await save()
    await postAnswerFeedback({ conversation_id: String(conversationId), message_index: index, oordeel, toelichting })
    setOordelen(prev => ({ ...prev, [index]: oordeel }))
  }, [conversationId, save])

  return { oordelen, submit }
}

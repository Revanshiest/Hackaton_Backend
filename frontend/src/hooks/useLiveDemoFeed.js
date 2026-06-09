import { useCallback, useEffect, useRef, useState } from 'react'
import liveDemoFeed from '../data/liveDemoFeed.json'

const MIN_INTERVAL_MS = 2800
const MAX_INTERVAL_MS = 6500
const MAX_VISIBLE = 5

function randomInterval() {
  return MIN_INTERVAL_MS + Math.floor(Math.random() * (MAX_INTERVAL_MS - MIN_INTERVAL_MS))
}

/**
 * Demo live-поток: по одному обращению из заранее собранного JSON.
 */
export function useLiveDemoFeed(enabled) {
  const poolRef = useRef([])
  const indexRef = useRef(0)
  const timerRef = useRef(null)
  const [events, setEvents] = useState([])
  const [received, setReceived] = useState(0)
  const [active, setActive] = useState(false)

  const pushNext = useCallback(() => {
    const pool = poolRef.current
    if (!pool.length) return

    const item = pool[indexRef.current % pool.length]
    indexRef.current += 1

    const event = {
      ...item,
      uid: `${item.id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      at: new Date().toISOString(),
    }

    setEvents((prev) => [event, ...prev].slice(0, MAX_VISIBLE))
    setReceived((n) => n + 1)
  }, [])

  const schedule = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      pushNext()
      schedule()
    }, randomInterval())
  }, [pushNext])

  useEffect(() => {
    if (!enabled) {
      setActive(false)
      if (timerRef.current) clearTimeout(timerRef.current)
      return undefined
    }

    const items = [...(liveDemoFeed.items || [])]
    poolRef.current = items
    indexRef.current = 0
    setEvents([])
    setReceived(0)
    setActive(true)

    pushNext()
    schedule()

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [enabled, pushNext, schedule])

  const dismiss = useCallback((uid) => {
    setEvents((prev) => prev.filter((e) => e.uid !== uid))
  }, [])

  const reset = useCallback(() => {
    indexRef.current = 0
    setEvents([])
    setReceived(0)
    if (enabled) pushNext()
  }, [enabled, pushNext])

  return {
    events,
    received,
    active,
    total: liveDemoFeed.count ?? liveDemoFeed.items?.length ?? 0,
    sourceFile: liveDemoFeed.source_file,
    dismiss,
    reset,
  }
}

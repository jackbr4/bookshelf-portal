import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { getMamStatus } from './api'
import type { MamStatus } from './types'

/** How often the sitewide status is refreshed from the backend. */
export const MAM_POLL_INTERVAL_MS = 60_000

/** Amber warning when free slots (relative to the block threshold) drop to this or below. */
export const MAM_WARN_SLOTS = 10

interface MamStatusContextValue {
  status: MamStatus | null
  /** Non-null when the last fetch failed (status is then whatever we last had). */
  error: string | null
  /** True when a torrent dispatch would currently be refused. */
  blocked: boolean
  /**
   * Seconds until the next slot frees, computed against the server clock.
   * null when unknown (no status, or no next_free_at). Clamped at 0.
   */
  secondsUntilFree: number | null
  /** (server clock − client clock) in seconds, captured at the last successful fetch. */
  serverOffsetSeconds: number
  /** Force an immediate refresh (e.g. after a 429). */
  refresh: () => Promise<void>
}

const defaultValue: MamStatusContextValue = {
  status: null,
  error: null,
  blocked: false,
  secondsUntilFree: null,
  serverOffsetSeconds: 0,
  refresh: async () => {},
}

const MamStatusContext = createContext<MamStatusContextValue>(defaultValue)

/**
 * Remaining seconds until `nextFreeAt`, using the server's clock. `offset`
 * is (server_time - client_time) captured when the status was fetched, so a
 * skewed client clock doesn't move the countdown.
 */
export function secondsUntil(nextFreeAt: number | null, offsetSeconds: number, nowMs = Date.now()): number | null {
  if (nextFreeAt == null) return null
  const serverNow = nowMs / 1000 + offsetSeconds
  return Math.max(0, Math.round(nextFreeAt - serverNow))
}

/** "2h 14m", "14m", or "under a minute". */
export function formatRemaining(seconds: number): string {
  if (seconds < 60) return 'under a minute'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`
  return `${m}m`
}

export function MamStatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<MamStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nowMs, setNowMs] = useState(() => Date.now())
  const offsetRef = useRef(0)
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const s = await getMamStatus()
      if (!mounted.current) return
      offsetRef.current = s.serverTime - Date.now() / 1000
      setStatus(s)
      setError(null)
      setNowMs(Date.now())
    } catch (err: unknown) {
      if (!mounted.current) return
      const msg = err instanceof Error ? err.message : String(err)
      // Session expiry is handled by the page's own API calls; don't
      // surface it as a slot-status problem.
      if (msg !== 'SESSION_EXPIRED') setError(msg || 'Could not load MAM status')
    }
  }, [])

  // Initial fetch + periodic poll.
  useEffect(() => {
    mounted.current = true
    refresh()
    const id = setInterval(refresh, MAM_POLL_INTERVAL_MS)
    return () => {
      mounted.current = false
      clearInterval(id)
    }
  }, [refresh])

  // 1 s tick drives the countdown, only while blocked (that's the only state
  // that displays one — no point re-rendering the tree every second
  // otherwise). When the countdown first hits zero, re-fetch once so the
  // banner clears without waiting for the next poll (the backend's own 30 s
  // cache may lag, so a stale next_free_at can come back — hence "once per
  // value", not every tick).
  const nextFreeAt = status?.nextFreeAt ?? null
  const isBlocked = status?.blocked ?? false
  const refreshedAtZeroFor = useRef<number | null>(null)
  useEffect(() => {
    if (nextFreeAt == null || !isBlocked) return
    const id = setInterval(() => {
      const t = Date.now()
      setNowMs(t)
      if (secondsUntil(nextFreeAt, offsetRef.current, t) === 0 && refreshedAtZeroFor.current !== nextFreeAt) {
        refreshedAtZeroFor.current = nextFreeAt
        refresh()
      }
    }, 1000)
    return () => clearInterval(id)
  }, [nextFreeAt, isBlocked, refresh])

  const value: MamStatusContextValue = {
    status,
    error,
    blocked: status?.blocked ?? false,
    secondsUntilFree: secondsUntil(nextFreeAt, offsetRef.current, nowMs),
    serverOffsetSeconds: offsetRef.current,
    refresh,
  }

  return <MamStatusContext.Provider value={value}>{children}</MamStatusContext.Provider>
}

export function useMamStatus(): MamStatusContextValue {
  return useContext(MamStatusContext)
}

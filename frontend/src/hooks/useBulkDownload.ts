import { useCallback, useMemo, useRef, useState } from 'react'
import { useMamStatus, formatRemaining, secondsUntil } from '../lib/mamStatus'
import type { DispatchResult, DownloadTarget } from './useDownloader'
import type { ImportResolveItem, ToastState } from '../lib/types'

/** One selectable row: a specific release for a specific book. */
export interface BulkTarget extends DownloadTarget {
  item: ImportResolveItem
}

export type RowOutcome =
  | { kind: 'sending' }
  | { kind: 'waiting'; nextFreeAt: number | null }
  | { kind: 'failed'; message: string }

interface Args {
  dispatch: (t: DownloadTarget) => Promise<DispatchResult>
  showToast: (t: ToastState) => void
  /** Called with each guid that was accepted by the download client. */
  onSent: (guid: string) => void
}

/**
 * Selection + slot-aware sequential dispatch for the import page.
 *
 * Before sending, the MAM status is re-fetched. Usenet rows always go;
 * torrent rows go until the fresh `slots_free` is used up (or the backend
 * answers 429 mid-run), and the rest are marked "waiting for slot". Waiting
 * rows stay selected so a second click sends them once slots free up.
 */
export function useBulkDownload({ dispatch, showToast, onSent }: Args) {
  const mam = useMamStatus()
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [outcomes, setOutcomes] = useState<Map<string, RowOutcome>>(() => new Map())
  const [running, setRunning] = useState<{ done: number; total: number } | null>(null)
  const cancelled = useRef(false)

  const toggle = useCallback((guid: string, on: boolean) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (on) next.add(guid)
      else next.delete(guid)
      return next
    })
    if (!on) setOutcomes(prev => {
      if (!prev.has(guid)) return prev
      const next = new Map(prev)
      next.delete(guid)
      return next
    })
  }, [])

  const selectMany = useCallback((guids: string[]) => {
    setSelected(prev => {
      const next = new Set(prev)
      guids.forEach(g => next.add(g))
      return next
    })
  }, [])

  const clear = useCallback(() => {
    setSelected(new Set())
    setOutcomes(prev => {
      // Keep failure notes visible; drop waiting markers since nothing is queued now.
      const next = new Map<string, RowOutcome>()
      prev.forEach((v, k) => { if (v.kind === 'failed') next.set(k, v) })
      return next
    })
  }, [])

  const setOutcome = (guid: string, o: RowOutcome | null) =>
    setOutcomes(prev => {
      const next = new Map(prev)
      if (o) next.set(guid, o)
      else next.delete(guid)
      return next
    })

  const run = useCallback(async (targets: BulkTarget[]) => {
    const queue = targets.filter(t => selected.has(t.release.guid))
    if (!queue.length || running) return
    cancelled.current = false
    setRunning({ done: 0, total: queue.length })

    // Fresh slot count. Fail closed for torrents if it can't be verified.
    const status = await mam.refresh()
    let torrentBudget: number
    if (!status || status.unsatisfied == null) {
      torrentBudget = 0
    } else {
      torrentBudget = Math.max(0, status.slotsFree ?? 0)
    }
    let nextFreeAt: number | null = status?.nextFreeAt ?? null

    let sent = 0
    let waiting = 0
    let failed = 0
    let duplicates = 0
    let done = 0

    for (const t of queue) {
      if (cancelled.current) break
      const guid = t.release.guid
      const isTorrent = t.release.protocol === 'torrent'

      if (isTorrent && torrentBudget <= 0) {
        setOutcome(guid, { kind: 'waiting', nextFreeAt })
        waiting++
        done++
        setRunning({ done, total: queue.length })
        continue
      }

      setOutcome(guid, { kind: 'sending' })
      const result = await dispatch(t)
      done++
      setRunning({ done, total: queue.length })

      if (result.ok) {
        sent++
        if (isTorrent) torrentBudget--
        setOutcome(guid, null)
        onSent(guid)
        setSelected(prev => { const n = new Set(prev); n.delete(guid); return n })
        continue
      }
      switch (result.kind) {
        case 'session':
          return
        case 'blocked':
          // Our budget was stale; stop sending torrents for this run.
          torrentBudget = 0
          nextFreeAt = result.nextFreeAt ?? nextFreeAt
          setOutcome(guid, { kind: 'waiting', nextFreeAt })
          waiting++
          break
        case 'duplicate':
          duplicates++
          setOutcome(guid, null)
          onSent(guid) // it's in the client either way
          setSelected(prev => { const n = new Set(prev); n.delete(guid); return n })
          break
        case 'error':
          failed++
          setOutcome(guid, { kind: 'failed', message: result.message })
          break
      }
    }

    setRunning(null)

    const parts = [
      sent ? `${sent} sent` : null,
      duplicates ? `${duplicates} already in rTorrent` : null,
      waiting ? `${waiting} waiting for a MAM slot` : null,
      failed ? `${failed} failed` : null,
    ].filter(Boolean)
    const secs = waiting ? secondsUntil(nextFreeAt, mam.serverOffsetSeconds) : null
    showToast({
      kind: failed ? 'error' : waiting ? 'info' : 'success',
      message: sent ? `Sent ${sent} download${sent === 1 ? '' : 's'}` : waiting ? 'Waiting for MAM slots' : 'Nothing sent',
      subMessage: [
        parts.join(' · '),
        waiting ? (secs != null ? `Next slot frees in ${formatRemaining(secs)} — they stay selected.` : 'They stay selected until a slot frees.') : null,
      ].filter(Boolean).join(' '),
    })
  }, [selected, running, mam, dispatch, showToast, onSent])

  const cancel = useCallback(() => { cancelled.current = true }, [])

  const selectedCount = selected.size
  const waitingText = useMemo(() => {
    const secs = mam.secondsUntilFree
    return secs != null ? `Waiting for slot · ${formatRemaining(secs)}` : 'Waiting for slot'
  }, [mam.secondsUntilFree])

  return { selected, selectedCount, outcomes, running, waitingText, toggle, selectMany, clear, run, cancel }
}

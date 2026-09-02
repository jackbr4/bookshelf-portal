import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { alreadyInClientDetail, downloadRelease, mamBlockedDetail } from '../lib/api'
import { clearSession } from '../lib/session'
import { formatRemaining, secondsUntil, useMamStatus } from '../lib/mamStatus'
import type { MediaType, ReleaseItem, ToastState } from '../lib/types'

export interface DownloadTarget {
  title: string
  author: string
  release: ReleaseItem
  mediaType: MediaType
}

export type DispatchResult =
  | { ok: true; message: string }
  | { ok: false; kind: 'blocked'; message: string; nextFreeAt: number | null }
  | { ok: false; kind: 'duplicate'; message: string }
  | { ok: false; kind: 'session' }
  | { ok: false; kind: 'error'; message: string }

/**
 * Shared "send a release to the download client" behaviour: toast on
 * success/failure, session-expiry redirect, and the MAM 429 handling
 * (countdown in the toast + immediate status refresh so the banner flips).
 *
 * `download` does all of that and resolves true/false. `dispatch` is the
 * silent building block (no toast) for callers that batch several sends
 * and want to summarise themselves; it still redirects on session expiry
 * and refreshes MAM status on a 429.
 */
export function useDownloader() {
  const navigate = useNavigate()
  const mam = useMamStatus()
  const [toast, setToast] = useState<ToastState | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const showToast = useCallback((t: ToastState) => {
    if (timer.current) clearTimeout(timer.current)
    setToast(t)
    timer.current = setTimeout(() => setToast(null), 5000)
  }, [])

  const dismissToast = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    setToast(null)
  }, [])

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  const dispatch = useCallback(async ({ title, author, release, mediaType }: DownloadTarget): Promise<DispatchResult> => {
    try {
      const res = await downloadRelease({
        title,
        author,
        releaseTitle: release.title,
        indexer: release.indexer,
        protocol: release.protocol,
        downloadUrl: release.downloadUrl,
        mediaType,
      })
      return { ok: true, message: res.message }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        clearSession()
        navigate('/', { replace: true })
        return { ok: false, kind: 'session' }
      }
      const blocked = mamBlockedDetail(err)
      if (blocked) {
        // The backend refused the dispatch at MAM's slot cap. Pull fresh
        // status so the sitewide banner flips immediately.
        mam.refresh()
        return { ok: false, kind: 'blocked', message: msg, nextFreeAt: blocked.nextFreeAt }
      }
      const dup = alreadyInClientDetail(err)
      if (dup) return { ok: false, kind: 'duplicate', message: dup.message }
      return { ok: false, kind: 'error', message: msg || 'Please try again in a few minutes.' }
    }
  }, [navigate, mam])

  const download = useCallback(async (target: DownloadTarget): Promise<boolean> => {
    const result = await dispatch(target)
    if (result.ok) {
      showToast({ kind: 'success', message: 'Download started', subMessage: result.message })
      return true
    }
    switch (result.kind) {
      case 'session':
        break
      case 'blocked': {
        const secs = secondsUntil(result.nextFreeAt, mam.serverOffsetSeconds)
        showToast({
          kind: 'error',
          message: 'MAM download limit reached — downloads are paused',
          subMessage: secs != null ? `Next slot frees in ${formatRemaining(secs)}.` : 'Waiting for current downloads to finish.',
        })
        break
      }
      case 'duplicate':
        showToast({ kind: 'info', message: 'Already in rTorrent', subMessage: result.message })
        break
      case 'error':
        showToast({ kind: 'error', message: 'Download failed', subMessage: result.message })
        break
    }
    return false
  }, [dispatch, mam, showToast])

  return { toast, showToast, dismissToast, download, dispatch }
}

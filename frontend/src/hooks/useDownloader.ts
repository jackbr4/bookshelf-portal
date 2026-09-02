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

/**
 * Shared "send a release to the download client" behaviour: toast on
 * success/failure, session-expiry redirect, and the MAM 429 handling
 * (countdown in the toast + immediate status refresh so the banner flips).
 *
 * Returns the toast state for the page to render, and `download`, which
 * resolves true on success and false on any handled failure.
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

  const download = useCallback(async ({ title, author, release, mediaType }: DownloadTarget): Promise<boolean> => {
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
      showToast({ kind: 'success', message: 'Download started', subMessage: res.message })
      return true
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        clearSession()
        navigate('/', { replace: true })
        return false
      }
      const blocked = mamBlockedDetail(err)
      if (blocked) {
        // The backend refused the dispatch at MAM's slot cap. Pull fresh
        // status so the sitewide banner flips immediately, and echo the
        // countdown here, against the server clock.
        mam.refresh()
        const secs = secondsUntil(blocked.nextFreeAt, mam.serverOffsetSeconds)
        showToast({
          kind: 'error',
          message: 'MAM download limit reached — downloads are paused',
          subMessage: secs != null ? `Next slot frees in ${formatRemaining(secs)}.` : 'Waiting for current downloads to finish.',
        })
        return false
      }
      const dup = alreadyInClientDetail(err)
      if (dup) {
        showToast({
          kind: 'info',
          message: 'Already in rTorrent',
          subMessage: dup.message,
        })
        return false
      }
      showToast({
        kind: 'error',
        message: 'Download failed',
        subMessage: msg || 'Please try again in a few minutes.',
      })
      return false
    }
  }, [navigate, mam, showToast])

  return { toast, showToast, dismissToast, download }
}

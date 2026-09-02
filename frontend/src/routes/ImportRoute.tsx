import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PortalHeader from '../components/PortalHeader'
import PortalToast from '../components/PortalToast'
import ImportInputCard, { type ImportInputMode } from '../components/ImportInputCard'
import ImportReviewTable, { newRow, type ReviewRow } from '../components/ImportReviewTable'
import ImportResults from '../components/ImportResults'
import { extractList, extractErrorDetail, startResolve, getResolveStatus, cancelResolve, logout } from '../lib/api'
import { clearSession } from '../lib/session'
import { useDownloader } from '../hooks/useDownloader'
import type { ImportResolveItem, ImportResolveStatus, MediaType, ReleaseItem } from '../lib/types'

type Stage = 'input' | 'review' | 'results'

/** How often the results stage polls the resolve job. */
export const RESOLVE_POLL_MS = 1500

export default function ImportRoute() {
  const navigate = useNavigate()
  const { toast, showToast, dismissToast, download } = useDownloader()

  const [stage, setStage] = useState<Stage>('input')
  const [inputMode, setInputMode] = useState<ImportInputMode>('url')
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState<{ message: string; offerPaste: boolean } | null>(null)

  const [rows, setRows] = useState<ReviewRow[]>([])
  const [sourceTitle, setSourceTitle] = useState<string | null>(null)

  const [job, setJob] = useState<ImportResolveStatus | null>(null)
  const jobIdRef = useRef<string | null>(null)
  const [downloadingGuid, setDownloadingGuid] = useState<string | null>(null)
  const [sentGuids, setSentGuids] = useState<Set<string>>(() => new Set())

  const handleSessionExpired = useCallback(() => {
    clearSession()
    navigate('/', { replace: true })
  }, [navigate])

  // ---------------------------------------------------------------------
  // Stage 1: extract
  // ---------------------------------------------------------------------

  async function handleExtract(input: { url: string } | { text: string }) {
    setExtracting(true)
    setExtractError(null)
    try {
      const res = await extractList(input)
      setRows(res.books.map(b => newRow(b)))
      setSourceTitle(res.sourceTitle ?? null)
      setStage('review')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        handleSessionExpired()
        return
      }
      const detail = extractErrorDetail(err)
      setExtractError({
        message: detail?.message || msg || 'Something went wrong. Please try again.',
        offerPaste: detail?.code === 'fetch_failed' || detail?.code === 'no_content',
      })
    } finally {
      setExtracting(false)
    }
  }

  // ---------------------------------------------------------------------
  // Stage 3: resolve job + polling
  // ---------------------------------------------------------------------

  const stopJob = useCallback(() => {
    const id = jobIdRef.current
    jobIdRef.current = null
    if (id) cancelResolve(id)
  }, [])

  async function handleFind() {
    const books = rows
      .map(r => ({ title: r.title.trim(), author: r.author.trim() }))
      .filter(b => b.title || b.author)
    if (!books.length) return
    stopJob()
    try {
      const { jobId, total } = await startResolve(books)
      jobIdRef.current = jobId
      setJob({
        jobId,
        done: false,
        total,
        completed: 0,
        results: books.map((b, i) => ({ index: i, title: b.title, author: b.author, status: 'pending' })),
      })
      setStage('results')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        handleSessionExpired()
        return
      }
      showToast({ kind: 'error', message: "Couldn't start the availability check", subMessage: msg })
    }
  }

  // Poll while a job is running. Cancelled jobs stop the loop via jobIdRef.
  useEffect(() => {
    if (stage !== 'results' || !job || job.done) return
    const jobId = job.jobId
    let cancelled = false
    const tick = async () => {
      if (cancelled || jobIdRef.current !== jobId) return
      try {
        const status = await getResolveStatus(jobId)
        if (cancelled || jobIdRef.current !== jobId) return
        setJob(status)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        if (msg === 'SESSION_EXPIRED') {
          handleSessionExpired()
          return
        }
        // Job expired or the server restarted: mark everything still pending as failed.
        setJob(prev => prev && {
          ...prev,
          done: true,
          completed: prev.total,
          results: prev.results.map(r => (r.status === 'pending' ? { ...r, status: 'error', error: msg || 'Lost track of this check' } : r)),
        })
      }
    }
    const id = setInterval(tick, RESOLVE_POLL_MS)
    tick()
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [stage, job?.jobId, job?.done, handleSessionExpired])

  // Leaving the page cancels any running job.
  useEffect(() => () => stopJob(), [stopJob])

  // ---------------------------------------------------------------------
  // Navigation between stages
  // ---------------------------------------------------------------------

  function handleStartOver() {
    stopJob()
    setJob(null)
    setRows([])
    setSourceTitle(null)
    setExtractError(null)
    setStage('input')
  }

  function handleBackToReview() {
    stopJob()
    setJob(null)
    setStage('review')
  }

  const handleDownload = useCallback(async (item: ImportResolveItem, release: ReleaseItem, mediaType: MediaType) => {
    setDownloadingGuid(release.guid)
    try {
      const ok = await download({ title: item.title, author: item.author, release, mediaType })
      if (ok) setSentGuids(prev => new Set(prev).add(release.guid))
    } finally {
      setDownloadingGuid(null)
    }
  }, [download])

  async function handleLogout() {
    stopJob()
    await logout()
    clearSession()
    navigate('/', { replace: true })
  }

  return (
    <div className="portal-page">
      <PortalHeader
        title="Import a list"
        showImport={false}
        backLink={{ to: '/request', label: '← back to requests' }}
        onSignOut={handleLogout}
      />

      <main className="portal-main">
        {stage === 'input' && (
          <ImportInputCard
            mode={inputMode}
            onModeChange={setInputMode}
            loading={extracting}
            error={extractError}
            onSubmit={handleExtract}
          />
        )}

        {stage === 'review' && (
          <ImportReviewTable
            rows={rows}
            sourceTitle={sourceTitle}
            onChange={setRows}
            onFind={handleFind}
            onStartOver={handleStartOver}
          />
        )}

        {stage === 'results' && job && (
          <ImportResults
            job={job}
            downloadingGuid={downloadingGuid}
            sentGuids={sentGuids}
            onDownload={handleDownload}
            onBackToReview={handleBackToReview}
            onStartOver={handleStartOver}
          />
        )}
      </main>

      {toast && (
        <PortalToast
          kind={toast.kind}
          message={toast.message}
          subMessage={toast.subMessage}
          actionLabel={toast.actionLabel}
          onAction={toast.onAction}
          onDismiss={dismissToast}
        />
      )}
    </div>
  )
}

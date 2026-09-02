import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import PortalHeader from '../components/PortalHeader'
import SearchCard from '../components/SearchCard'
import ReleaseResults from '../components/ReleaseResults'
import PortalToast from '../components/PortalToast'
import { getReleases, downloadRelease, logout, mamBlockedDetail } from '../lib/api'
import { clearSession } from '../lib/session'
import { formatRemaining, secondsUntil, useMamStatus } from '../lib/mamStatus'
import type { ReleasesResponse, ToastState, ReleaseItem, MediaType } from '../lib/types'

export default function RequestRoute() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [results, setResults] = useState<ReleasesResponse | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [lastTitle, setLastTitle] = useState('')
  const [lastAuthor, setLastAuthor] = useState('')
  const mam = useMamStatus()

  function showToast(t: ToastState) {
    setToast(t)
    setTimeout(() => setToast(null), 5000)
  }

  function handleSessionExpired() {
    clearSession()
    navigate('/', { replace: true })
  }

  const handleSearch = useCallback(async () => {
    if (!title.trim() && !author.trim()) return
    setSearching(true)
    setSearchError(null)
    setResults(null)
    setLastTitle(title.trim())
    setLastAuthor(author.trim())
    try {
      const data = await getReleases(title.trim(), author.trim())
      setResults(data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        handleSessionExpired()
        return
      }
      setSearchError(msg || 'Something went wrong. Please try again.')
    } finally {
      setSearching(false)
    }
  }, [title, author, navigate])

  function handleClear() {
    setTitle('')
    setAuthor('')
    setResults(null)
    setSearchError(null)
    setLastTitle('')
    setLastAuthor('')
  }

  const handleDownload = useCallback(async (release: ReleaseItem, mediaType: MediaType) => {
    try {
      const res = await downloadRelease({
        title: lastTitle || title.trim(),
        author: lastAuthor || author.trim(),
        releaseTitle: release.title,
        indexer: release.indexer,
        protocol: release.protocol,
        downloadUrl: release.downloadUrl,
        mediaType,
      })
      showToast({
        kind: 'success',
        message: 'Download started',
        subMessage: res.message,
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        handleSessionExpired()
        return
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
          subMessage:
            secs != null
              ? `Next slot frees in ${formatRemaining(secs)}.`
              : 'Waiting for current downloads to finish.',
        })
        return
      }
      showToast({
        kind: 'error',
        message: 'Download failed',
        subMessage: msg || 'Please try again in a few minutes.',
      })
    }
  }, [lastTitle, lastAuthor, title, author, navigate, mam])

  async function handleLogout() {
    await logout()
    clearSession()
    navigate('/', { replace: true })
  }

  return (
    <div className="portal-page">
      <PortalHeader title="Book Request Portal" onSignOut={handleLogout} />

      <main className="portal-main">
        <SearchCard
          title={title}
          author={author}
          onTitleChange={setTitle}
          onAuthorChange={setAuthor}
          onSearch={handleSearch}
          onClear={handleClear}
          hasResults={!!results}
          loading={searching}
          error={searchError ?? undefined}
        />

        {results && (
          <div style={{ marginTop: 28 }}>
            <ReleaseResults
              results={results}
              searchTitle={lastTitle}
              searchAuthor={lastAuthor}
              onDownload={handleDownload}
            />
          </div>
        )}
      </main>

      {toast && (
        <PortalToast
          kind={toast.kind}
          message={toast.message}
          subMessage={toast.subMessage}
          actionLabel={toast.actionLabel}
          onAction={toast.onAction}
          onDismiss={() => setToast(null)}
        />
      )}
    </div>
  )
}

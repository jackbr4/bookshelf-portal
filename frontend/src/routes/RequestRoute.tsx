import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import PortalHeader from '../components/PortalHeader'
import SearchCard from '../components/SearchCard'
import ReleaseResults from '../components/ReleaseResults'
import PortalToast from '../components/PortalToast'
import { getReleases, logout } from '../lib/api'
import { clearSession } from '../lib/session'
import { useDownloader } from '../hooks/useDownloader'
import type { ReleasesResponse, ReleaseItem, MediaType } from '../lib/types'

export default function RequestRoute() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [results, setResults] = useState<ReleasesResponse | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [lastTitle, setLastTitle] = useState('')
  const [lastAuthor, setLastAuthor] = useState('')
  const { toast, dismissToast, download } = useDownloader()

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
    await download({
      title: lastTitle || title.trim(),
      author: lastAuthor || author.trim(),
      release,
      mediaType,
    })
  }, [download, lastTitle, lastAuthor, title, author])

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
          onDismiss={dismissToast}
        />
      )}
    </div>
  )
}

import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import SearchPanel from '../components/SearchPanel'
import ResultsSection from '../components/ResultsSection'
import PortalToast from '../components/PortalToast'
import PortalButton from '../components/PortalButton'
import { search, addBook, addSeries, logout } from '../lib/api'
import { clearSession } from '../lib/session'
import type { SearchResults, ToastState, ItemStatus, BookResult, SeriesResult } from '../lib/types'

export default function RequestRoute() {
  const navigate = useNavigate()
  const [results, setResults] = useState<SearchResults | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [lastQuery, setLastQuery] = useState('')

  function showToast(t: ToastState) {
    setToast(t)
    setTimeout(() => setToast(null), 5000)
  }

  function handleSessionExpired() {
    clearSession()
    navigate('/', { replace: true })
  }

  const handleSearch = useCallback(async (query: string) => {
    setSearching(true)
    setSearchError(null)
    setResults(null)
    setLastQuery(query)
    try {
      const data = await search(query)
      setResults(data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        handleSessionExpired()
        return
      }
      setSearchError(msg && msg !== 'SESSION_EXPIRED' ? msg : 'Something went wrong. Please try again.')
    } finally {
      setSearching(false)
    }
  }, [])

  const handleAddBook = useCallback(async (item: BookResult | SeriesResult) => {
    const book = item as BookResult
    try {
      await addBook(book.id, book.title, book.author, book.foreignAuthorId, book.foreignEditionId)
      setResults(prev => {
        if (!prev) return prev
        return {
          ...prev,
          books: prev.books.map(b =>
            b.id === book.id ? { ...b, status: 'already_monitored' as ItemStatus } : b
          ),
        }
      })
      showToast({
        kind: 'success',
        message: 'Book added successfully',
        subMessage: 'Bookshelf will now monitor and search for this title. It may take up to 15 minutes before this book is available in Calibre.',
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') { handleSessionExpired(); return }
      if (msg === 'DUPLICATE') {
        showToast({ kind: 'info', message: 'This book is already in the library or being monitored.' })
      } else if (msg === 'AUTHOR_NOT_FOUND') {
        showToast({
          kind: 'error',
          message: 'Could not look up this book.',
          subMessage: 'Try searching with the full title and author name.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
        })
      } else if (msg === 'BOOKSHELF_ERROR') {
        showToast({
          kind: 'error',
          message: 'This book could not be added. Please try again in a few minutes.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
        })
      } else if (msg === 'CONNECTION_ERROR') {
        showToast({
          kind: 'error',
          message: 'Cannot reach Bookshelf.',
          subMessage: 'The library server is not responding. Please wait a moment and try again.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
        })
      } else {
        showToast({
          kind: 'error',
          message: 'Something went wrong while adding this book.',
          subMessage: 'Please try again. If the problem persists, try searching with the full title and author name.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
        })
      }
    }
  }, [])

  const handleAddSeries = useCallback(async (item: BookResult | SeriesResult) => {
    const seriesId = item.id
    try {
      await addSeries(seriesId)
      setResults(prev => {
        if (!prev) return prev
        return {
          ...prev,
          series: prev.series.map(s =>
            s.id === seriesId ? { ...s, status: 'already_monitored' as ItemStatus } : s
          ),
        }
      })
      showToast({
        kind: 'success',
        message: 'Series added successfully',
        subMessage: 'Bookshelf will now monitor the books in this series.',
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') { handleSessionExpired(); return }
      if (msg === 'DUPLICATE') {
        showToast({ kind: 'info', message: 'This series is already being monitored.' })
      } else {
        showToast({
          kind: 'error',
          message: 'Something went wrong while adding this series.',
          actionLabel: 'Retry',
          onAction: () => handleAddSeries(item),
        })
      }
    }
  }, [])

  async function handleLogout() {
    await logout()
    clearSession()
    navigate('/', { replace: true })
  }

  const hasBooks = (results?.books.length ?? 0) > 0
  const hasSeries = (results?.series.length ?? 0) > 0
  const noResults = results !== null && !hasBooks && !hasSeries

  return (
    <div className="min-vh-100" style={{ background: 'var(--color-page-bg)' }}>
      {/* Header */}
      <header className="bg-white border-bottom py-3 px-4 d-flex align-items-center justify-content-between">
        <div>
          <h1 className="h5 mb-0 fw-semibold">Book Request Portal</h1>
          <p className="text-muted mb-0" style={{ fontSize: '13px' }}>Request a book or series for download</p>
        </div>
        <PortalButton variant="outline-secondary" size="sm" onClick={handleLogout}>
          Sign out
        </PortalButton>
      </header>

      <main className="container py-5">
        <div className="search-panel">
          <SearchPanel onSearch={handleSearch} loading={searching} />

          {searchError && (
            <div className="alert alert-danger mt-3" role="alert">
              {searchError}
            </div>
          )}
        </div>

        {/* Results */}
        {results !== null && (
          <div className="mt-4">
            {noResults && !searching && (
              <div className="text-center py-5 text-muted">
                <div style={{ fontSize: '2rem' }}>📚</div>
                <p className="mt-2">No matching books or series found for <strong>"{lastQuery}"</strong></p>
              </div>
            )}

            {hasBooks && (
              <ResultsSection
                heading="Books"
                kind="book"
                items={results.books}
                onAdd={handleAddBook}
              />
            )}

            {hasSeries && (
              <div className={hasBooks ? 'mt-4' : ''}>
                <ResultsSection
                  heading="Series"
                  kind="series"
                  items={results.series}
                  onAdd={handleAddSeries}
                />
              </div>
            )}
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

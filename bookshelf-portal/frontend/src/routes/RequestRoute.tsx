import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import SearchPanel from '../components/SearchPanel'
import ResultsSection from '../components/ResultsSection'
import PortalToast from '../components/PortalToast'
import PortalButton from '../components/PortalButton'
import { search, addBook, logout } from '../lib/api'
import { clearSession } from '../lib/session'
import type { SearchResults, ToastState, ItemStatus, BookResult, SeriesResult } from '../lib/types'

function FilteredRow({ book, onAdd, last }: { book: BookResult; onAdd: (b: BookResult) => Promise<void>; last: boolean }) {
  const [adding, setAdding] = useState(false)
  const subtitle = [book.author, book.year ? String(book.year) : null, book.seriesName].filter(Boolean).join(' · ')

  async function handleAdd() {
    setAdding(true)
    try { await onAdd(book) } finally { setAdding(false) }
  }

  return (
    <div
      className={`d-flex align-items-center justify-content-between gap-2 px-3 py-2${last ? '' : ' border-bottom'}`}
      style={{ background: 'var(--color-card-bg, #fff)', minHeight: '48px' }}
    >
      <div style={{ minWidth: 0 }}>
        <span className="fw-medium" style={{ fontSize: '14px' }}>{book.title}</span>
        {subtitle && <span className="text-muted ms-2" style={{ fontSize: '12px' }}>{subtitle}</span>}
      </div>
      {book.status === 'available' ? (
        <PortalButton variant="outline-secondary" size="sm" loading={adding} onClick={handleAdd} style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>
          Add
        </PortalButton>
      ) : (
        <span className="text-muted" style={{ fontSize: '12px', flexShrink: 0 }}>
          {book.status === 'already_monitored' ? 'Monitored' : 'Added'}
        </span>
      )}
    </div>
  )
}

export default function RequestRoute() {
  const navigate = useNavigate()
  const [results, setResults] = useState<SearchResults | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [lastQuery, setLastQuery] = useState('')
  const [showFiltered, setShowFiltered] = useState(false)

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
    setShowFiltered(false)
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
            b.id === item.id ? { ...b, status: 'already_monitored' as ItemStatus } : b
          ),
          filteredBooks: prev.filteredBooks.map(b =>
            b.id === item.id ? { ...b, status: 'already_monitored' as ItemStatus } : b
          ),
        }
      })
      showToast({
        kind: 'success',
        message: 'Book added successfully',
        subMessage: 'Bookshelf will now monitor and search for this title. It may take up to 15 minutes before it appears in Calibre.',
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') { handleSessionExpired(); return }
      if (msg === 'DUPLICATE') {
        showToast({
          kind: 'info',
          message: 'This book is already in the library or being monitored.',
          subMessage: 'It should already be available or on its way to Calibre.',
        })
      } else if (msg === 'AUTHOR_NOT_FOUND') {
        showToast({
          kind: 'error',
          message: 'Could not look up this book.',
          subMessage: 'Try searching with the full title and author name, then add it again.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
        })
      } else if (msg === 'BOOKSHELF_ERROR') {
        showToast({
          kind: 'error',
          message: 'This book could not be added. Please try again in a few minutes.',
          subMessage: 'Bookshelf returned an error. If this keeps happening, let Brendan know.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
        })
      } else if (msg === 'CONNECTION_ERROR') {
        showToast({
          kind: 'error',
          message: 'Cannot reach Bookshelf.',
          subMessage: 'The server may be temporarily unavailable. Try again in a moment.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
        })
      } else {
        showToast({
          kind: 'error',
          message: 'Something went wrong while adding this book.',
          subMessage: 'Please try again. If the problem persists, let Brendan know.',
          actionLabel: 'Retry',
          onAction: () => handleAddBook(item),
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
  const hasFiltered = (results?.filteredBooks?.length ?? 0) > 0
  const noResults = results !== null && !hasBooks && !hasFiltered

  return (
    <div className="min-vh-100" style={{ background: 'var(--color-page-bg)' }}>
      {/* Header */}
      <header className="bg-white border-bottom py-3 px-4 d-flex align-items-center justify-content-between">
        <div>
          <h1 className="h5 mb-0 fw-semibold">Book Request Portal</h1>
          <p className="text-muted mb-0" style={{ fontSize: '13px' }}>Request a book for download</p>
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
                <p className="mt-2">No matching books found for <strong>"{lastQuery}"</strong></p>
                <p style={{ fontSize: '13px' }}>Try a different title or include the author's name.</p>
              </div>
            )}

            {hasBooks && (
              <ResultsSection
                heading="Best matches"
                kind="book"
                items={results.books}
                onAdd={handleAddBook}
              />
            )}

            {(results.filteredBooks?.length ?? 0) > 0 && (
              <div className="mt-3">
                <button
                  className="btn btn-link btn-sm p-0 text-decoration-none"
                  style={{ fontSize: '13px', color: 'var(--color-text-muted, #6c757d)' }}
                  onClick={() => setShowFiltered(v => !v)}
                >
                  {showFiltered ? '▾' : '▸'} {showFiltered ? 'Hide' : 'Show'} other results ({results.filteredBooks!.length})
                </button>
                {showFiltered && (
                  <div className="mt-2 border rounded" style={{ overflow: 'hidden' }}>
                    {results.filteredBooks!.map((book, i) => (
                      <FilteredRow
                        key={book.id}
                        book={book}
                        onAdd={handleAddBook}
                        last={i === results.filteredBooks!.length - 1}
                      />
                    ))}
                  </div>
                )}
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

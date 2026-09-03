import { useState, useRef } from 'react'
import PortalButton from './PortalButton'

export type SearchMode = 'book' | 'url' | 'text'

interface Props {
  title: string
  author: string
  onTitleChange: (value: string) => void
  onAuthorChange: (value: string) => void
  onSearch: () => void
  onClear?: () => void
  /** Hands a URL or pasted article off to the import flow. */
  onImport?: (input: { url: string } | { text: string }) => void
  /** Which tab to open on ("book" unless returning from an import "Start over"). */
  initialMode?: SearchMode
  hasResults?: boolean
  loading: boolean
  error?: string
}

const MODE_COPY: Record<SearchMode, { eyebrow: string; helper: string }> = {
  book: {
    eyebrow: 'SEARCH FOR BOOKS',
    helper: 'Search for ebooks and audiobooks by title and/or author.',
  },
  url: {
    eyebrow: 'IMPORT A BOOK LIST',
    helper: "Paste a link to an article with a list of books and we'll pull out the titles for you to review.",
  },
  text: {
    eyebrow: 'IMPORT A BOOK LIST',
    helper: "Paste the article or list text and we'll pull out the titles for you to review.",
  },
}

export default function SearchCard({
  title,
  author,
  onTitleChange,
  onAuthorChange,
  onSearch,
  onClear,
  onImport,
  initialMode,
  hasResults,
  loading,
  error,
}: Props) {
  const [mode, setMode] = useState<SearchMode>(initialMode ?? 'book')
  const [touched, setTouched] = useState(false)
  const [importUrl, setImportUrl] = useState('')
  const [importText, setImportText] = useState('')
  const titleRef = useRef<HTMLInputElement>(null)

  function switchMode(next: SearchMode) {
    setMode(next)
    setTouched(false)
  }

  function handleClear() {
    onClear?.()
    titleRef.current?.focus()
  }

  function handleSearch() {
    setTouched(true)
    if (!title.trim() && !author.trim()) return
    onSearch()
  }

  function handleImport() {
    setTouched(true)
    const value = (mode === 'url' ? importUrl : importText).trim()
    if (!value) return
    onImport?.(mode === 'url' ? { url: value } : { text: value })
  }

  const importValue = (mode === 'url' ? importUrl : importText).trim()
  const showError =
    touched && (mode === 'book' ? !title.trim() && !author.trim() : !importValue)

  const emptyMessage =
    mode === 'book'
      ? 'Enter a title and/or author to search.'
      : mode === 'url'
        ? 'Enter a URL to import from.'
        : 'Paste some text to import from.'

  return (
    <section className="search-card">
      <p className="search-card__eyebrow">{MODE_COPY[mode].eyebrow}</p>

      {onImport && (
        <div className="import-tabs search-card__tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'book'}
            className={`release-tab ${mode === 'book' ? 'release-tab--active' : ''}`}
            onClick={() => switchMode('book')}
          >
            One book
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'url'}
            className={`release-tab ${mode === 'url' ? 'release-tab--active' : ''}`}
            onClick={() => switchMode('url')}
          >
            From a URL
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'text'}
            className={`release-tab ${mode === 'text' ? 'release-tab--active' : ''}`}
            onClick={() => switchMode('text')}
          >
            Paste text
          </button>
        </div>
      )}

      <p className="search-card__helper">{MODE_COPY[mode].helper}</p>

      {mode === 'book' && (
        <div className="search-card__fields">
          <div>
            <label className="field-label" htmlFor="search-title">Title</label>
            <input
              ref={titleRef}
              id="search-title"
              className="field-input"
              placeholder="e.g. A Children's Bible"
              value={title}
              onChange={e => onTitleChange(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <div>
            <label className="field-label" htmlFor="search-author">Author</label>
            <input
              id="search-author"
              className="field-input"
              placeholder="e.g. Lydia Millet"
              value={author}
              onChange={e => onAuthorChange(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <PortalButton variant="primary" size="md" loading={loading} onClick={handleSearch}>
              Search
            </PortalButton>
            {hasResults && onClear && (
              <PortalButton variant="ghost" size="md" type="button" onClick={handleClear}>
                × Clear
              </PortalButton>
            )}
          </div>
        </div>
      )}

      {mode === 'url' && (
        <div className="import-input__row">
          <div style={{ flex: 1 }}>
            <label className="field-label" htmlFor="search-import-url">Article URL</label>
            <input
              id="search-import-url"
              className="field-input"
              type="url"
              inputMode="url"
              placeholder="https://www.theguardian.com/books/…"
              value={importUrl}
              onChange={e => setImportUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleImport()}
            />
          </div>
          <PortalButton variant="primary" size="md" onClick={handleImport}>
            Extract books
          </PortalButton>
        </div>
      )}

      {mode === 'text' && (
        <div>
          <label className="field-label" htmlFor="search-import-text">Article text</label>
          <textarea
            id="search-import-text"
            className="field-input import-textarea"
            placeholder="Paste the article or list here…"
            value={importText}
            onChange={e => setImportText(e.target.value)}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
            <PortalButton variant="primary" size="md" onClick={handleImport}>
              Extract books
            </PortalButton>
          </div>
        </div>
      )}

      {(showError || (error && mode === 'book')) && (
        <p className="field-error" role="alert">
          {(mode === 'book' && error) || emptyMessage}
        </p>
      )}
    </section>
  )
}

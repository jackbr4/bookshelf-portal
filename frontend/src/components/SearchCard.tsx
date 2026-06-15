import { useState } from 'react'
import PortalButton from './PortalButton'

interface Props {
  title: string
  author: string
  onTitleChange: (value: string) => void
  onAuthorChange: (value: string) => void
  onSearch: () => void
  onClear?: () => void
  hasResults?: boolean
  loading: boolean
  error?: string
}

export default function SearchCard({
  title,
  author,
  onTitleChange,
  onAuthorChange,
  onSearch,
  onClear,
  hasResults,
  loading,
  error,
}: Props) {
  const [touched, setTouched] = useState(false)

  function handleSearch() {
    setTouched(true)
    if (!title.trim() && !author.trim()) return
    onSearch()
  }

  const showError = touched && !title.trim() && !author.trim()

  return (
    <section className="search-card">
      <p className="search-card__eyebrow">SEARCH FOR BOOKS</p>
      <p className="search-card__helper">
        Search for ebooks and audiobooks by title and/or author.
      </p>

      <div className="search-card__fields">
        <div>
          <label className="field-label" htmlFor="search-title">Title</label>
          <input
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
            <PortalButton variant="ghost" size="md" type="button" onClick={onClear}>
              × Clear
            </PortalButton>
          )}
        </div>
      </div>

      {(showError || error) && (
        <p className="field-error" role="alert">
          {error || 'Enter a title and/or author to search.'}
        </p>
      )}
    </section>
  )
}

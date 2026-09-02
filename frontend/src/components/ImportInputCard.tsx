import { useState } from 'react'
import PortalButton from './PortalButton'

export type ImportInputMode = 'url' | 'text'

interface Props {
  mode: ImportInputMode
  onModeChange: (mode: ImportInputMode) => void
  loading: boolean
  /** Structured error from the last attempt; `offerPaste` adds a switch-to-paste action. */
  error?: { message: string; offerPaste: boolean } | null
  onSubmit: (input: { url: string } | { text: string }) => void
}

export default function ImportInputCard({ mode, onModeChange, loading, error, onSubmit }: Props) {
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [touched, setTouched] = useState(false)

  const value = mode === 'url' ? url.trim() : text.trim()
  const showEmpty = touched && !value

  function submit() {
    setTouched(true)
    if (!value) return
    onSubmit(mode === 'url' ? { url: value } : { text: value })
  }

  return (
    <section className="search-card" data-testid="import-input">
      <p className="search-card__eyebrow">IMPORT A BOOK LIST</p>
      <p className="search-card__helper">
        Paste a link to an article with a list of books, or paste the text itself, and we'll pull out the
        titles for you to review.
      </p>

      <div className="import-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'url'}
          className={`release-tab ${mode === 'url' ? 'release-tab--active' : ''}`}
          onClick={() => { onModeChange('url'); setTouched(false) }}
        >
          Article URL
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'text'}
          className={`release-tab ${mode === 'text' ? 'release-tab--active' : ''}`}
          onClick={() => { onModeChange('text'); setTouched(false) }}
        >
          Paste text
        </button>
      </div>

      {mode === 'url' ? (
        <div className="import-input__row">
          <div style={{ flex: 1 }}>
            <label className="field-label" htmlFor="import-url">Article URL</label>
            <input
              id="import-url"
              className="field-input"
              type="url"
              inputMode="url"
              placeholder="https://www.theguardian.com/books/…"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submit()}
              disabled={loading}
            />
          </div>
          <PortalButton variant="primary" size="md" loading={loading} onClick={submit}>
            Extract books
          </PortalButton>
        </div>
      ) : (
        <div>
          <label className="field-label" htmlFor="import-text">Article text</label>
          <textarea
            id="import-text"
            className="field-input import-textarea"
            placeholder="Paste the article or list here…"
            value={text}
            onChange={e => setText(e.target.value)}
            disabled={loading}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
            <PortalButton variant="primary" size="md" loading={loading} onClick={submit}>
              Extract books
            </PortalButton>
          </div>
        </div>
      )}

      {showEmpty && !error && (
        <p className="field-error" role="alert">
          {mode === 'url' ? 'Enter a URL to import from.' : 'Paste some text to import from.'}
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error.message}
          {error.offerPaste && mode === 'url' && (
            <>
              {' '}
              <button
                type="button"
                className="link-button"
                onClick={() => { onModeChange('text'); setTouched(false) }}
              >
                Paste the text instead
              </button>
            </>
          )}
        </p>
      )}
    </section>
  )
}

import PortalButton from './PortalButton'
import type { BookCandidate } from '../lib/types'

export interface ReviewRow extends BookCandidate {
  /** Stable key for React; rows can be added/removed while editing. */
  key: string
}

interface Props {
  rows: ReviewRow[]
  sourceTitle?: string | null
  includeAudiobooks: boolean
  onChange: (rows: ReviewRow[]) => void
  onIncludeAudiobooksChange: (value: boolean) => void
  onFind: () => void
  onStartOver: () => void
}

let nextKey = 1
export function newRow(partial: Partial<BookCandidate> = {}): ReviewRow {
  return { key: `row-${nextKey++}`, title: '', author: '', confidence: 'high', ...partial }
}

export default function ImportReviewTable({ rows, sourceTitle, includeAudiobooks, onChange, onIncludeAudiobooksChange, onFind, onStartOver }: Props) {
  const usable = rows.filter(r => r.title.trim() || r.author.trim()).length
  const lowCount = rows.filter(r => r.confidence === 'low').length

  function update(key: string, patch: Partial<BookCandidate>) {
    onChange(rows.map(r => (r.key === key ? { ...r, ...patch } : r)))
  }

  function remove(key: string) {
    onChange(rows.filter(r => r.key !== key))
  }

  return (
    <section className="search-card" data-testid="import-review">
      <p className="search-card__eyebrow">REVIEW THE LIST</p>
      <p className="search-card__helper">
        {sourceTitle ? <>From <strong>{sourceTitle}</strong>. </> : null}
        Found {rows.length} book{rows.length === 1 ? '' : 's'}. Fix anything that looks off, remove what you
        don't want, then find out what's available.
        {lowCount > 0 && (
          <> <span className="confidence-dot" aria-hidden="true" /> marks {lowCount} we weren't sure about.</>
        )}
      </p>

      {rows.length === 0 ? (
        <div className="empty-state" style={{ padding: '28px 20px' }}>
          <p style={{ margin: 0 }}>No books in the list. Add one below or start over.</p>
        </div>
      ) : (
        <div className="import-table" role="table" aria-label="Books to import">
          <div className="import-table__head" role="row">
            <span role="columnheader" className="import-table__num">#</span>
            <span role="columnheader">Title</span>
            <span role="columnheader">Author</span>
            <span role="columnheader" className="import-table__actions" />
          </div>
          {rows.map((row, i) => (
            <div className="import-table__row" role="row" key={row.key} data-testid="review-row">
              <span className="import-table__num" role="cell">
                {i + 1}
                {row.confidence === 'low' && (
                  <span
                    className="confidence-dot"
                    title="We weren't sure about this one — check the title and author"
                    data-testid="confidence-low"
                  />
                )}
              </span>
              <span role="cell">
                <input
                  className="field-input field-input--compact"
                  aria-label={`Title ${i + 1}`}
                  value={row.title}
                  onChange={e => update(row.key, { title: e.target.value })}
                />
              </span>
              <span role="cell">
                <input
                  className="field-input field-input--compact"
                  aria-label={`Author ${i + 1}`}
                  placeholder="(unknown)"
                  value={row.author}
                  onChange={e => update(row.key, { author: e.target.value })}
                />
              </span>
              <span role="cell" className="import-table__actions">
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Remove ${row.title || `row ${i + 1}`}`}
                  onClick={() => remove(row.key)}
                >
                  ×
                </button>
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="import-review__footer">
        <PortalButton variant="ghost" size="sm" type="button" onClick={() => onChange([...rows, newRow()])}>
          + Add a book
        </PortalButton>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label className="import-review__toggle">
            <input
              type="checkbox"
              checked={includeAudiobooks}
              onChange={e => onIncludeAudiobooksChange(e.target.checked)}
            />
            Include audiobooks
          </label>
          <PortalButton variant="ghost" size="md" type="button" onClick={onStartOver}>
            Start over
          </PortalButton>
          <PortalButton variant="primary" size="md" disabled={usable === 0} onClick={onFind}>
            Find availability ({usable})
          </PortalButton>
        </div>
      </div>
    </section>
  )
}

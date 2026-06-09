import { useState } from 'react'
import type { BookResult, SeriesResult } from '../lib/types'
import StatusBadge from './StatusBadge'
import PortalButton from './PortalButton'

type Kind = 'book' | 'series'

interface Props {
  kind: Kind
  item: BookResult | SeriesResult
  onAdd: (item: BookResult | SeriesResult) => Promise<void>
}

export default function ResultCard({ kind, item, onAdd }: Props) {
  const [adding, setAdding] = useState(false)
  const canAdd = item.status === 'available'

  const subtitleLines: string[] = []
  if (kind === 'book') {
    const book = item as BookResult
    const parts = [book.author]
    if (book.year) parts.push(String(book.year))
    if (book.seriesName) parts.push(book.seriesName)
    subtitleLines.push(parts.join(' · '))
  } else {
    const s = item as SeriesResult
    const parts = [s.author]
    if (s.bookCount) parts.push(`${s.bookCount} books`)
    subtitleLines.push(parts.join(' · '))
  }

  async function handleAdd() {
    setAdding(true)
    try {
      await onAdd(item)
    } finally {
      setAdding(false)
    }
  }

  const coverUrl = 'coverUrl' in item ? item.coverUrl : null

  return (
    <div className="result-card p-3 d-flex gap-3 align-items-start">
      {/* Cover */}
      <div>
        {coverUrl ? (
          <img src={coverUrl} alt="" className="cover-img" />
        ) : (
          <div className="cover-placeholder">
            {kind === 'book' ? '📖' : '📚'}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-grow-1 min-width-0">
        <div className="d-flex align-items-start justify-content-between gap-2 flex-wrap">
          <div>
            <p className="mb-0 fw-semibold" style={{ fontSize: '15px', lineHeight: '1.3' }}>
              {item.title}
            </p>
            {subtitleLines.map((line, i) => (
              <p key={i} className="mb-0 text-muted" style={{ fontSize: '13px' }}>
                {line}
              </p>
            ))}
          </div>
          <StatusBadge status={item.status} />
        </div>

        <div className="mt-2">
          {canAdd ? (
            <PortalButton
              variant="primary"
              size="sm"
              loading={adding}
              onClick={handleAdd}
            >
              {kind === 'book' ? 'Add Book' : 'Add Series'}
            </PortalButton>
          ) : (
            <PortalButton variant="secondary" size="sm" disabled>
              {item.status === 'already_monitored' ? 'Already Monitored' : 'Already Added'}
            </PortalButton>
          )}
        </div>
      </div>
    </div>
  )
}

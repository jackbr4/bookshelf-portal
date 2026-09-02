import ImportBookCard, { topPicks, type BulkSelectionProps } from './ImportBookCard'
import PortalButton from './PortalButton'
import type { ImportResolveItem, ImportResolveStatus, MediaType, ReleaseItem } from '../lib/types'

interface Props {
  job: ImportResolveStatus
  downloadingGuid: string | null
  sentGuids: ReadonlySet<string>
  bulk: BulkSelectionProps & {
    running: { done: number; total: number } | null
    onSelectAllEbooks: () => void
    onClear: () => void
    onDownloadSelected: () => void
  }
  onDownload: (item: ImportResolveItem, release: ReleaseItem, mediaType: MediaType) => Promise<void>
  onBackToReview: () => void
  onStartOver: () => void
}

export default function ImportResults({ job, downloadingGuid, sentGuids, bulk, onDownload, onBackToReview, onStartOver }: Props) {
  const pct = job.total ? Math.round((job.completed / job.total) * 100) : 0
  const counts = job.results.reduce(
    (acc, r) => ({ ...acc, [r.status]: (acc[r.status] ?? 0) + 1 }),
    {} as Partial<Record<ImportResolveItem['status'], number>>
  )

  const summary = job.done
    ? [
        counts.available ? `${counts.available} available` : null,
        counts.in_library ? `${counts.in_library} already in library` : null,
        counts.requested ? `${counts.requested} already requested` : null,
        counts.not_found ? `${counts.not_found} not found` : null,
        counts.error ? `${counts.error} failed` : null,
      ].filter(Boolean).join(' · ')
    : `Checking ${job.completed} of ${job.total}…`

  // Rows that could be bulk-selected (not yet sent)
  const selectable = job.results.flatMap(item =>
    topPicks(item).filter(p => !sentGuids.has(p.release.guid))
  )
  const selectedCount = selectable.filter(p => bulk.selected.has(p.release.guid)).length
  const allEbooksSelected = selectable
    .filter(p => p.mediaType === 'ebook')
    .every(p => bulk.selected.has(p.release.guid))

  return (
    <section data-testid="import-results">
      <div className="import-progress" aria-live="polite">
        <div className="import-progress__row">
          <p className="import-progress__summary" data-testid="import-summary">{summary}</p>
          <div style={{ display: 'flex', gap: 8 }}>
            <PortalButton variant="ghost" size="sm" type="button" onClick={onBackToReview}>
              ← Edit list
            </PortalButton>
            <PortalButton variant="ghost" size="sm" type="button" onClick={onStartOver}>
              Start over
            </PortalButton>
          </div>
        </div>
        <div
          className="import-progress__bar"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={job.total}
          aria-valuenow={job.completed}
        >
          <div className={`import-progress__fill ${job.done ? 'import-progress__fill--done' : ''}`} style={{ width: `${pct}%` }} />
        </div>

        {selectable.length > 0 && (
          <div className="import-bulk" data-testid="import-bulk">
            <div className="import-bulk__links">
              {!allEbooksSelected && (
                <button type="button" className="link-button" onClick={bulk.onSelectAllEbooks} disabled={!!bulk.running}>
                  Select all ebooks
                </button>
              )}
              {selectedCount > 0 && (
                <button type="button" className="link-button" onClick={bulk.onClear} disabled={!!bulk.running}>
                  Clear selection
                </button>
              )}
              {selectedCount === 0 && allEbooksSelected && (
                <span className="import-bulk__hint">Tick the releases you want, then download them together.</span>
              )}
            </div>
            <PortalButton
              variant="primary"
              size="md"
              disabled={selectedCount === 0}
              loading={!!bulk.running}
              onClick={bulk.onDownloadSelected}
            >
              {bulk.running
                ? `Sending ${bulk.running.done} of ${bulk.running.total}…`
                : `Download selected (${selectedCount})`}
            </PortalButton>
          </div>
        )}
      </div>

      <div className="import-book-list">
        {job.results.map(item => (
          <ImportBookCard
            key={item.index}
            item={item}
            downloadingGuid={downloadingGuid}
            sentGuids={sentGuids}
            bulk={bulk}
            onDownload={onDownload}
          />
        ))}
      </div>
    </section>
  )
}

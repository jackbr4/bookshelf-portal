import { useState } from 'react'
import ReleaseCard from './ReleaseCard'
import ReleaseResults from './ReleaseResults'
import { describeHistory } from '../lib/historyText'
import type { RowOutcome } from '../hooks/useBulkDownload'
import type { ImportResolveItem, MediaType, ReleaseItem } from '../lib/types'

export interface BulkSelectionProps {
  selected: ReadonlySet<string>
  outcomes: ReadonlyMap<string, RowOutcome>
  waitingText: string
  onToggle: (guid: string, on: boolean) => void
}

interface Props {
  item: ImportResolveItem
  /** guid currently being dispatched, if any */
  downloadingGuid: string | null
  /** guids already sent to the download client this session */
  sentGuids: ReadonlySet<string>
  /** Bulk-select state for the top picks; omit to hide checkboxes. */
  bulk?: BulkSelectionProps
  onDownload: (item: ImportResolveItem, release: ReleaseItem, mediaType: MediaType) => Promise<void>
}

/**
 * The rows a book contributes to bulk selection: its best ebook and best
 * audiobook. Only "available" books — in-library and previously-requested
 * ones keep their releases behind the expander, where downloads are one at
 * a time on purpose.
 */
export function topPicks(item: ImportResolveItem): Array<{ release: ReleaseItem; mediaType: MediaType }> {
  if (item.status !== 'available') return []
  const out: Array<{ release: ReleaseItem; mediaType: MediaType }> = []
  const eb = item.releases?.ebookAccepted[0]
  const ab = item.releases?.audiobookAccepted[0]
  if (eb) out.push({ release: eb, mediaType: 'ebook' })
  if (ab) out.push({ release: ab, mediaType: 'audiobook' })
  return out
}

const STATUS_LABEL: Record<ImportResolveItem['status'], string> = {
  pending: 'Checking…',
  in_library: 'In library',
  requested: 'Requested',
  available: 'Available',
  not_found: 'Not found',
  error: 'Error',
}

export default function ImportBookCard({ item, downloadingGuid, sentGuids, bulk, onDownload }: Props) {
  const [showAll, setShowAll] = useState(false)
  const rel = item.releases
  const topEbook = rel?.ebookAccepted[0]
  const topAudio = rel?.audiobookAccepted[0]
  const totalAccepted = (rel?.ebookAccepted.length ?? 0) + (rel?.audiobookAccepted.length ?? 0)
  const hasReleases = totalAccepted > 0

  function rowProps(release: ReleaseItem, mediaType: MediaType) {
    if (!bulk) return {}
    const outcome = bulk.outcomes.get(release.guid)
    return {
      selection: {
        checked: bulk.selected.has(release.guid),
        onChange: (on: boolean) => bulk.onToggle(release.guid, on),
        label: `Select ${mediaType} for ${item.title}`,
      },
      rowState:
        outcome?.kind === 'waiting'
          ? { kind: 'waiting' as const, text: bulk.waitingText }
          : outcome?.kind === 'failed'
            ? { kind: 'failed' as const, text: `Failed: ${outcome.message}` }
            : null,
      downloading: downloadingGuid === release.guid || outcome?.kind === 'sending',
    }
  }

  return (
    <article className={`import-book import-book--${item.status}`} data-testid="import-book" data-status={item.status}>
      <header className="import-book__head">
        <div className="import-book__title-wrap">
          <span className="import-book__num">{item.index + 1}</span>
          <div>
            <h3 className="import-book__title">{item.title || <em>Untitled</em>}</h3>
            {item.author && <p className="import-book__author">{item.author}</p>}
          </div>
        </div>
        <span className={`status-badge import-status import-status--${item.status}`}>
          {item.status === 'pending' && <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />}
          {STATUS_LABEL[item.status]}
        </span>
      </header>

      {item.status === 'error' && (
        <p className="import-book__note import-book__note--error">{item.error || 'Something went wrong looking this one up.'}</p>
      )}

      {item.status === 'not_found' && (
        <p className="import-book__note">No matching releases found. Try tweaking the title or author on the request page.</p>
      )}

      {/* Collapsed-state banners; the expanded ReleaseResults shows its own. */}
      {item.status === 'in_library' && rel && !showAll && (
        <div className="import-book__library">
          {rel.calibreTitle && <div className="library-banner" style={{ marginTop: 0 }}>Already in Calibre: {rel.calibreTitle}</div>}
          {rel.audiobooksTitle && <div className="library-banner" style={{ marginTop: rel.calibreTitle ? 8 : 0 }}>Already in Audiobookshelf: {rel.audiobooksTitle}</div>}
        </div>
      )}

      {item.status === 'requested' && rel?.historyMatch && !showAll && (
        <div className="import-book__library">
          <div className="library-banner library-banner--history" style={{ marginTop: 0 }} data-testid="history-banner">
            {describeHistory(rel.historyMatch)}
            {rel.historyMatch.releaseTitle && (
              <span className="library-banner__detail"> — {rel.historyMatch.releaseTitle}</span>
            )}
          </div>
        </div>
      )}

      {hasReleases && item.status === 'available' && !showAll && (
        <div className="import-book__top">
          {topEbook && (
            <div>
              <p className="section-eyebrow import-book__eyebrow">BEST EBOOK</p>
              <ReleaseCard
                release={topEbook}
                viewMode="simple"
                downloading={downloadingGuid === topEbook.guid}
                sent={sentGuids.has(topEbook.guid)}
                onDownload={r => onDownload(item, r, 'ebook')}
                {...rowProps(topEbook, 'ebook')}
              />
            </div>
          )}
          {topAudio && (
            <div>
              <p className="section-eyebrow import-book__eyebrow">BEST AUDIOBOOK</p>
              <ReleaseCard
                release={topAudio}
                viewMode="simple"
                downloading={downloadingGuid === topAudio.guid}
                sent={sentGuids.has(topAudio.guid)}
                onDownload={r => onDownload(item, r, 'audiobook')}
                {...rowProps(topAudio, 'audiobook')}
              />
            </div>
          )}
        </div>
      )}

      {hasReleases && showAll && rel && (
        <div className="import-book__all">
          <ReleaseResults
            results={rel}
            searchTitle={item.title}
            searchAuthor={item.author}
            onDownload={(r, mt) => onDownload(item, r, mt)}
            downloadingGuid={downloadingGuid}
            sentGuids={sentGuids}
          />
        </div>
      )}

      {hasReleases && (item.status === 'available' || item.status === 'in_library' || item.status === 'requested') && (
        <button type="button" className="link-button import-book__toggle" onClick={() => setShowAll(v => !v)}>
          {showAll
            ? 'Show fewer'
            : item.status === 'available'
              ? `Show all ${totalAccepted} release${totalAccepted === 1 ? '' : 's'}`
              : `Show ${totalAccepted} release${totalAccepted === 1 ? '' : 's'} anyway`}
        </button>
      )}
    </article>
  )
}

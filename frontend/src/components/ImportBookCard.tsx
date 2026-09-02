import { useState } from 'react'
import ReleaseCard from './ReleaseCard'
import ReleaseResults from './ReleaseResults'
import type { ImportResolveItem, MediaType, ReleaseItem } from '../lib/types'

interface Props {
  item: ImportResolveItem
  /** guid currently being dispatched, if any */
  downloadingGuid: string | null
  /** guids already sent to the download client this session */
  sentGuids: ReadonlySet<string>
  onDownload: (item: ImportResolveItem, release: ReleaseItem, mediaType: MediaType) => Promise<void>
}

const STATUS_LABEL: Record<ImportResolveItem['status'], string> = {
  pending: 'Checking…',
  in_library: 'In library',
  available: 'Available',
  not_found: 'Not found',
  error: 'Error',
}

export default function ImportBookCard({ item, downloadingGuid, sentGuids, onDownload }: Props) {
  const [showAll, setShowAll] = useState(false)
  const rel = item.releases
  const topEbook = rel?.ebookAccepted[0]
  const topAudio = rel?.audiobookAccepted[0]
  const totalAccepted = (rel?.ebookAccepted.length ?? 0) + (rel?.audiobookAccepted.length ?? 0)
  const hasReleases = totalAccepted > 0

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

      {item.status === 'in_library' && rel && (
        <div className="import-book__library">
          {rel.calibreTitle && <div className="library-banner" style={{ marginTop: 0 }}>Already in Calibre: {rel.calibreTitle}</div>}
          {rel.audiobooksTitle && <div className="library-banner" style={{ marginTop: rel.calibreTitle ? 8 : 0 }}>Already in Audiobookshelf: {rel.audiobooksTitle}</div>}
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

      {hasReleases && (item.status === 'available' || item.status === 'in_library') && (
        <button type="button" className="link-button import-book__toggle" onClick={() => setShowAll(v => !v)}>
          {showAll
            ? 'Show fewer'
            : item.status === 'in_library'
              ? `Show ${totalAccepted} release${totalAccepted === 1 ? '' : 's'} anyway`
              : `Show all ${totalAccepted} release${totalAccepted === 1 ? '' : 's'}`}
        </button>
      )}
    </article>
  )
}

import { useMemo, useState } from 'react'
import type { MediaType, ReleasesResponse, ReleaseItem, ViewMode } from '../lib/types'
import ReleaseCard from './ReleaseCard'

interface Props {
  results: ReleasesResponse
  searchTitle: string
  searchAuthor: string
  onDownload: (release: ReleaseItem, mediaType: MediaType) => Promise<void>
  /** Optional: let a parent own the in-flight guid (e.g. the import page tracks one across many cards). */
  downloadingGuid?: string | null
  /** Optional: releases already sent this session, shown as "Sent" instead of a button. */
  sentGuids?: ReadonlySet<string>
}

export default function ReleaseResults({
  results,
  searchTitle,
  searchAuthor,
  onDownload,
  downloadingGuid: controlledDownloading,
  sentGuids,
}: Props) {
  const [activeTab, setActiveTab] = useState<MediaType>('ebook')
  const [viewMode, setViewMode] = useState<ViewMode>('simple')
  const [localDownloading, setLocalDownloading] = useState<string | null>(null)
  const downloadingGuid = controlledDownloading !== undefined ? controlledDownloading : localDownloading

  const ebookCount = results.ebookAccepted.length
  const audioCount = results.audiobookAccepted.length
  const accepted = activeTab === 'ebook' ? results.ebookAccepted : results.audiobookAccepted
  const rejected = activeTab === 'ebook' ? results.ebookRejected : results.audiobookRejected

  const summary = useMemo(() => {
    const filtered = rejected.length
    return `${accepted.length} release${accepted.length === 1 ? '' : 's'} found${filtered ? ` · ${filtered} filtered out` : ''}`
  }, [accepted.length, rejected.length])

  async function handleDownload(release: ReleaseItem) {
    setLocalDownloading(release.guid)
    try {
      await onDownload(release, activeTab)
    } finally {
      setLocalDownloading(null)
    }
  }

  if (!ebookCount && !audioCount) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon">📚</div>
        <p>No matching releases found for <strong>{searchTitle || searchAuthor}</strong>.</p>
      </div>
    )
  }

  return (
    <section>
      {results.calibreTitle && activeTab === 'ebook' && (
        <div className="library-banner">Already in Calibre: {results.calibreTitle}</div>
      )}
      {results.audiobooksTitle && activeTab === 'audiobook' && (
        <div className="library-banner">Already in Audiobookshelf: {results.audiobooksTitle}</div>
      )}

      <div className="release-tabs">
        <button
          type="button"
          className={`release-tab ${activeTab === 'ebook' ? 'release-tab--active' : ''}`}
          onClick={() => setActiveTab('ebook')}
        >
          <span>▥ Ebook</span>
          <span className="release-tab__count">{ebookCount}</span>
        </button>
        <button
          type="button"
          className={`release-tab ${activeTab === 'audiobook' ? 'release-tab--active' : ''}`}
          onClick={() => setActiveTab('audiobook')}
        >
          <span>◴ Audiobook</span>
          <span className="release-tab__count">{audioCount}</span>
        </button>
      </div>

      <div className="release-toolbar">
        <p className="release-toolbar__summary">{summary}</p>
        <div className="release-toolbar__actions">
<div className="view-toggle">
            <button
              type="button"
              className={`view-toggle__btn ${viewMode === 'simple' ? 'view-toggle__btn--active' : ''}`}
              onClick={() => setViewMode('simple')}
            >
              Simple
            </button>
            <button
              type="button"
              className={`view-toggle__btn ${viewMode === 'detailed' ? 'view-toggle__btn--active' : ''}`}
              onClick={() => setViewMode('detailed')}
            >
              Detailed
            </button>
          </div>
        </div>
      </div>

      <p className="section-eyebrow">{accepted.length} RELEASES FOUND</p>

      <div className="release-list">
        {accepted.map(release => (
          <ReleaseCard
            key={release.guid}
            release={release}
            viewMode={viewMode}
            downloading={downloadingGuid === release.guid}
            sent={sentGuids?.has(release.guid) ?? false}
            onDownload={handleDownload}
          />
        ))}
      </div>
    </section>
  )
}

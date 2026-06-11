import type { ReleaseItem, ViewMode } from '../lib/types'
import PortalButton from './PortalButton'

interface Props {
  release: ReleaseItem
  viewMode: ViewMode
  downloading: boolean
  onDownload: (release: ReleaseItem) => void
}

function formatMeta(release: ReleaseItem): string {
  const parts: string[] = []
  parts.push(`${release.sizeMb.toFixed(1)} MB`)
  if (release.protocol === 'torrent' && release.seeders != null) {
    parts.push(`${release.seeders} seeds`)
  }
  if (release.ageDays != null) {
    parts.push(`${release.ageDays}d old`)
  }
  return parts.join(' · ')
}

export default function ReleaseCard({ release, viewMode, downloading, onDownload }: Props) {
  const format = release.detectedFormat?.toUpperCase() ?? 'FILE'

  return (
    <article className="release-card">
      {viewMode === 'simple' ? (
        <div className="release-card__main release-card__main--simple">
          <span className="chip chip--format">{format}</span>
          <h3 className="release-card__title">{release.title}</h3>
        </div>
      ) : (
        <div className="release-card__main">
          <h3 className="release-card__title">{release.title}</h3>
          <div className="release-card__chips">
            <span className="chip chip--format">{format}</span>
            <span className="chip">{release.indexer}</span>
            <span className="chip">{formatMeta(release)}</span>
            {release.score > 0 && <span className="chip chip--score">{release.score}</span>}
          </div>
        </div>
      )}
      <div className="release-card__aside">
        {viewMode === 'detailed' && release.score > 0 && (
          <span className="release-card__score">{release.score}</span>
        )}
        <PortalButton
          variant="primary"
          size="sm"
          loading={downloading}
          onClick={() => onDownload(release)}
        >
          Download
        </PortalButton>
      </div>
    </article>
  )
}

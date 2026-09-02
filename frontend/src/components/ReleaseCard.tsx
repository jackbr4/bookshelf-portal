import type { ReleaseItem, ViewMode } from '../lib/types'
import { useMamStatus } from '../lib/mamStatus'
import PortalButton from './PortalButton'

interface Props {
  release: ReleaseItem
  viewMode: ViewMode
  downloading: boolean
  /** Already sent to the download client this session — button becomes a "Sent" marker. */
  sent?: boolean
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

export default function ReleaseCard({ release, viewMode, downloading, sent = false, onDownload }: Props) {
  const format = release.detectedFormat?.toUpperCase() ?? 'FILE'
  // Torrent dispatch is refused while MAM is at its slot cap; usenet never
  // counts against MAM so those buttons stay live.
  const { blocked: mamBlocked } = useMamStatus()
  const slotBlocked = mamBlocked && release.protocol === 'torrent'

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
        {sent ? (
          <span className="status-badge" title="Sent to the download client">✓ Sent</span>
        ) : (
          <PortalButton
            variant="primary"
            size="sm"
            loading={downloading}
            disabled={slotBlocked}
            title={slotBlocked ? 'MAM download limit reached — see the notice above for when downloads resume' : undefined}
            onClick={() => onDownload(release)}
          >
            Download
          </PortalButton>
        )}
      </div>
    </article>
  )
}

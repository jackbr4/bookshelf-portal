import type { HistoryItem, MediaFilter, SeedingItem, StatFilter } from '../lib/types'
import { formatRemaining, MAM_WARN_SLOTS, useMamStatus } from '../lib/mamStatus'
import {
  buildSeedingMap,
  computeMetrics,
  filterHistory,
  formatHistoryDate,
  seedTimeLeft,
  statusClass,
  statusLabel,
} from '../lib/adminUtils'

interface Props {
  items: HistoryItem[]
  seeding: SeedingItem[]
  statFilter: StatFilter
  mediaFilter: MediaFilter
  onStatFilterChange: (filter: StatFilter) => void
  onMediaFilterChange: (filter: MediaFilter) => void
}

function protocolChip(protocol?: string | null) {
  if (protocol === 'torrent') return <span className="chip chip--torrent">torrent</span>
  if (protocol === 'usenet') return <span className="chip chip--usenet">usenet</span>
  return null
}

function mediaChip(mediaType?: string | null) {
  if (mediaType === 'ebook') return <span className="chip chip--ebook">e-book</span>
  if (mediaType === 'audiobook') return <span className="chip">audio book</span>
  return null
}

export default function HistoryPanel({
  items,
  seeding,
  statFilter,
  mediaFilter,
  onStatFilterChange,
  onMediaFilterChange,
}: Props) {
  const { hashes, info } = buildSeedingMap(seeding)
  const metrics = computeMetrics(items, hashes)
  const filtered = filterHistory(items, statFilter, mediaFilter, hashes)

  const metricCards: Array<{
    key: StatFilter
    label: string
    value: number
    valueClass?: string
  }> = [
    { key: 'all', label: 'TOTAL REQUESTED', value: metrics.total },
    { key: 'imported', label: 'IN LIBRARY', value: metrics.imported, valueClass: 'metric-card__value--accent' },
    { key: 'active', label: 'IN PROGRESS', value: metrics.active, valueClass: 'metric-card__value--blue' },
    { key: 'errors', label: 'ERRORS', value: metrics.errors, valueClass: 'metric-card__value--error' },
    { key: 'seeding', label: 'SEEDING', value: metrics.seeding, valueClass: 'metric-card__value--teal' },
  ]

  return (
    <section>
      <div className="admin-metrics">
        {metricCards.map(card => (
          <button
            key={card.key}
            type="button"
            className={`metric-card ${statFilter === card.key ? 'metric-card--active' : ''}`}
            onClick={() => onStatFilterChange(card.key)}
          >
            <div className={`metric-card__value ${card.valueClass ?? ''}`}>{card.value}</div>
            <div className="metric-card__label">{card.label}</div>
          </button>
        ))}
        <MamSlotsCard />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <div className="media-filter">
          {([
            ['all', 'All'],
            ['ebook', 'E-book'],
            ['audiobook', 'Audio book'],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`media-filter__btn ${mediaFilter === key ? 'media-filter__btn--active' : ''}`}
              onClick={() => onMediaFilterChange(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="section-eyebrow" style={{ margin: 0 }}>
          {filtered.length} DOWNLOAD{filtered.length === 1 ? '' : 'S'}
        </p>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state__icon">▱</div>
          <p>No items match this filter.</p>
        </div>
      ) : (
        <div className="release-list">
          {filtered.map(item => {
            const hash = (item.downloadId || '').toUpperCase()
            const isSeeding = item.protocol === 'torrent' && hashes.has(hash)
            const seedLeft = isSeeding ? seedTimeLeft(info[hash]?.finishedAt) : null

            return (
              <article key={item.id} className="history-row">
                <div>
                  <h3 className="history-row__title">{item.title}</h3>
                  <p className="history-row__subtitle">
                    {item.releaseTitle || (item.author ? `by ${item.author}` : '')}
                  </p>
                  <div className="history-row__tags">
                    {protocolChip(item.protocol)}
                    {item.indexer && <span className="chip">{item.indexer}</span>}
                    {mediaChip(item.mediaType)}
                    {item.source && <span className="chip">{item.source}</span>}
                    {isSeeding && <span className="chip chip--seeding">seeding</span>}
                  </div>
                </div>
                <div className="history-row__meta">
                  <span className={statusClass(item.status)}>{statusLabel(item.status)}</span>
                  <p className="history-row__time">{formatHistoryDate(item.createdAt)}</p>
                  {seedLeft && <p className="history-row__seed">{seedLeft}</p>}
                  {item.error && <p className="history-row__error">⚠ {item.error}</p>}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

/**
 * MAM slot headroom, shown alongside the history metrics. Not a filter —
 * it's the same live status the header pill shows, in card form.
 */
function MamSlotsCard() {
  const { status, error, blocked, secondsUntilFree } = useMamStatus()

  let value: string
  let valueClass = ''
  let detail: string
  let tone = ''

  if (!status) {
    value = '—'
    detail = error ? 'Status unavailable' : 'Loading…'
  } else if (status.unsatisfied == null) {
    value = '—'
    valueClass = 'metric-card__value--error'
    detail = 'rTorrent unreachable · downloads paused'
    tone = 'metric-card--danger'
  } else if (blocked) {
    value = '0'
    valueClass = 'metric-card__value--error'
    detail = secondsUntilFree != null
      ? `${status.unsatisfied}/${status.limit} · next slot in ${formatRemaining(secondsUntilFree)}`
      : `${status.unsatisfied}/${status.limit} · waiting for downloads`
    tone = 'metric-card--danger'
  } else {
    value = String(status.slotsFree ?? '—')
    const warn = status.slotsFree != null && status.slotsFree <= MAM_WARN_SLOTS
    valueClass = warn ? 'metric-card__value--warning' : 'metric-card__value--teal'
    detail = `${status.unsatisfied}/${status.limit} used`
    tone = warn ? 'metric-card--warning' : ''
  }

  return (
    <div
      className={`metric-card metric-card--static ${tone}`}
      title={status ? `Unsatisfied = downloading or seeded < 72h. Downloads pause at ${status.blockThreshold}.` : undefined}
      data-testid="mam-slots-card"
    >
      <div className={`metric-card__value ${valueClass}`}>{value}</div>
      <div className="metric-card__label">MAM SLOTS</div>
      <div className="metric-card__detail">{detail}</div>
    </div>
  )
}

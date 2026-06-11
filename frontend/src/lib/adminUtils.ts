import type { HistoryItem, MediaFilter, SeedingItem, StatFilter } from './types'

export function formatHistoryDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function seedTimeLeft(finishedAt?: number): string | null {
  if (!finishedAt) return null
  const deadline = finishedAt + 72 * 3600
  const remaining = deadline - Math.floor(Date.now() / 1000)
  if (remaining <= 0) return null
  const days = Math.floor(remaining / 86400)
  const hours = Math.floor((remaining % 86400) / 3600)
  return `Seed: ${days}d ${hours}h left`
}

export function buildSeedingMap(seeding: SeedingItem[]) {
  const hashes = new Set<string>()
  const info: Record<string, { finishedAt?: number }> = {}
  for (const item of seeding) {
    const h = item.hash.toUpperCase()
    hashes.add(h)
    info[h] = { finishedAt: item.finishedAt }
  }
  return { hashes, info }
}

export function computeMetrics(items: HistoryItem[], seedingHashes: Set<string>) {
  const imported = items.filter(i => i.status === 'imported').length
  const active = items.filter(i => i.status === 'downloading' || i.status === 'importing').length
  const errors = items.filter(i => i.status === 'error').length
  const seeding = items.filter(
    i => i.protocol === 'torrent' && seedingHashes.has((i.downloadId || '').toUpperCase())
  ).length
  return {
    total: items.length,
    imported,
    active,
    errors,
    seeding,
  }
}

export function filterHistory(
  items: HistoryItem[],
  statFilter: StatFilter,
  mediaFilter: MediaFilter,
  seedingHashes: Set<string>
): HistoryItem[] {
  let filtered = items

  if (mediaFilter === 'ebook') {
    filtered = filtered.filter(i => i.mediaType === 'ebook')
  } else if (mediaFilter === 'audiobook') {
    filtered = filtered.filter(i => i.mediaType === 'audiobook')
  }

  if (statFilter === 'imported') {
    filtered = filtered.filter(i => i.status === 'imported')
  } else if (statFilter === 'active') {
    filtered = filtered.filter(i => i.status === 'downloading' || i.status === 'importing')
  } else if (statFilter === 'errors') {
    filtered = filtered.filter(i => i.status === 'error')
  } else if (statFilter === 'seeding') {
    filtered = filtered.filter(
      i => i.protocol === 'torrent' && seedingHashes.has((i.downloadId || '').toUpperCase())
    )
  }

  return filtered
}

export function statusLabel(status: string): string {
  if (status === 'imported') return '• IMPORTED'
  if (status === 'error') return '• ERROR'
  if (status === 'downloading' || status === 'importing') return '• IN PROGRESS'
  return `• ${status.toUpperCase()}`
}

export function statusClass(status: string): string {
  if (status === 'error') return 'status-badge status-badge--error'
  if (status === 'downloading' || status === 'importing') return 'status-badge status-badge--progress'
  return 'status-badge'
}

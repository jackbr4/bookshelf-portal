import type { HistoryMatch } from './types'

/** "just now", "3 hours ago", "2 days ago", "3 weeks ago", or a date beyond ~2 months. */
export function relativeTime(iso: string, nowMs = Date.now()): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const s = Math.max(0, Math.round((nowMs - t) / 1000))
  if (s < 90) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`
  const h = Math.round(m / 60)
  if (h < 36) return `${h} hour${h === 1 ? '' : 's'} ago`
  const d = Math.round(h / 24)
  if (d < 14) return `${d} day${d === 1 ? '' : 's'} ago`
  const w = Math.round(d / 7)
  if (w < 9) return `${w} week${w === 1 ? '' : 's'} ago`
  return new Date(t).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

/**
 * One line describing a past download of this book, e.g.
 * "Requested 3 days ago · audiobook · still downloading".
 */
export function describeHistory(h: HistoryMatch, nowMs = Date.now()): string {
  const when = relativeTime(h.createdAt, nowMs)
  const media = h.mediaType === 'audiobook' ? 'audiobook' : h.mediaType === 'ebook' ? 'ebook' : null
  const state = h.status === 'imported' ? 'imported' : h.status === 'downloading' ? 'still downloading' : h.status
  return ['Requested ' + when, media, state].filter(Boolean).join(' · ')
}

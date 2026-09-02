import { formatRemaining, MAM_WARN_SLOTS, useMamStatus } from '../lib/mamStatus'

/**
 * Compact slot indicator for the header. Hidden while status is still
 * loading. The Admin → Status tab carries the full detail.
 */
export function MamStatusPill() {
  const { status, error, blocked, secondsUntilFree } = useMamStatus()

  if (!status) {
    if (!error) return null
    return (
      <span className="mam-pill mam-pill--unknown" title={error}>
        MAM slots: unavailable
      </span>
    )
  }

  if (blocked) {
    const when = status.unsatisfied == null
      ? 'rTorrent unreachable'
      : secondsUntilFree != null
        ? `next slot in ${formatRemaining(secondsUntilFree)}`
        : 'waiting for downloads'
    return (
      <span
        className="mam-pill mam-pill--blocked"
        title="Requesting a torrent now would trigger a 24-hour MAM account block, so torrent downloads are paused. Usenet is unaffected."
        data-testid="mam-pill"
      >
        MAM slots: <strong>paused</strong>
        <span className="mam-pill__detail">({when})</span>
      </span>
    )
  }

  const warn = status.slotsFree != null && status.slotsFree <= MAM_WARN_SLOTS
  return (
    <span
      className={`mam-pill ${warn ? 'mam-pill--warn' : ''}`}
      title={`${status.unsatisfied}/${status.limit} unsatisfied torrents (downloading or seeded < 72h). Downloads pause at ${status.blockThreshold}.`}
      data-testid="mam-pill"
    >
      MAM slots: <strong>{status.slotsFree} free</strong>
      <span className="mam-pill__detail">({status.unsatisfied}/{status.limit} seeding)</span>
    </span>
  )
}


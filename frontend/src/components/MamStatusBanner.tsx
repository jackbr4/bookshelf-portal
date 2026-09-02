import { formatRemaining, MAM_WARN_SLOTS, useMamStatus } from '../lib/mamStatus'

/**
 * Compact slot indicator for the header. Hidden while blocked — the full
 * banner below the header takes over — and while status is still loading.
 */
export function MamStatusPill() {
  const { status, error, blocked } = useMamStatus()
  if (blocked) return null

  if (!status) {
    if (!error) return null
    return (
      <span className="mam-pill mam-pill--unknown" title={error}>
        MAM slots: unavailable
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

/**
 * Sitewide red banner shown only while torrent dispatch is blocked, with a
 * live countdown to the next slot freeing.
 */
export function MamBlockedBanner() {
  const { status, blocked, secondsUntilFree } = useMamStatus()
  if (!blocked || !status) return null

  const unverifiable = status.unsatisfied == null

  return (
    <div className="mam-banner" role="alert" data-testid="mam-banner">
      <div className="mam-banner__inner">
        <span className="mam-banner__icon" aria-hidden="true">⚠</span>
        <div>
          {unverifiable ? (
            <>
              <p className="mam-banner__title">MAM slot status unavailable — downloads are paused</p>
              <p className="mam-banner__body">
                The download client could not be reached, so free slots can't be verified. Torrent downloads
                stay paused until it's back; usenet downloads are unaffected.
              </p>
            </>
          ) : (
            <>
              <p className="mam-banner__title">
                MAM download limit reached ({status.unsatisfied}/{status.limit} unsatisfied)
              </p>
              <p className="mam-banner__body">
                Requesting a download now would trigger a 24-hour account block — torrent downloads are paused.{' '}
                {secondsUntilFree != null ? (
                  <>
                    Next slot frees in <strong className="mam-banner__countdown">{formatRemaining(secondsUntilFree)}</strong>.
                  </>
                ) : (
                  <>Waiting for current downloads to finish.</>
                )}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

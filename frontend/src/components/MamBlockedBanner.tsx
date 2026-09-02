import { formatRemaining, useMamStatus } from '../lib/mamStatus'

/**
 * Sitewide red banner, rendered under the header on every page but only
 * while torrent dispatch is blocked (MAM at its cap, or rTorrent
 * unreachable). Shows nothing otherwise — day-to-day slot info lives on
 * the Admin → Status tab.
 */
export default function MamBlockedBanner() {
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

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { MamStatus } from '../lib/types'

vi.mock('../lib/api', () => ({
  getMamStatus: vi.fn(),
}))

import { getMamStatus } from '../lib/api'
import { MamStatusProvider, formatRemaining, secondsUntil, MAM_POLL_INTERVAL_MS } from '../lib/mamStatus'
import ReleaseCard from '../components/ReleaseCard'
import MamBlockedBanner from '../components/MamBlockedBanner'
import PortalHeader from '../components/PortalHeader'
import HistoryPanel from '../components/HistoryPanel'

const NOW_MS = 1_800_000_000_000
const NOW_S = NOW_MS / 1000

function status(overrides: Partial<MamStatus> = {}): MamStatus {
  return {
    unsatisfied: 100,
    limit: 150,
    blockThreshold: 145,
    slotsFree: 45,
    blocked: false,
    nextFreeAt: NOW_S + 5 * 3600,
    serverTime: NOW_S,
    ...overrides,
  }
}

const torrentRelease = {
  guid: 'r1',
  title: 'Dune by Frank Herbert [ENG / EPUB]',
  indexer: 'MyAnonamouse',
  protocol: 'torrent',
  sizeMb: 1.2,
  detectedFormat: 'EPUB',
  seeders: 42,
  ageDays: 10,
  downloadUrl: 'https://example.com/r1',
  score: 70,
}

function renderWithProvider(ui: React.ReactNode) {
  return render(
    <MemoryRouter>
      <MamStatusProvider>{ui}</MamStatusProvider>
    </MemoryRouter>
  )
}

describe('mamStatus helpers', () => {
  it('formatRemaining renders h/m granularity', () => {
    expect(formatRemaining(2 * 3600 + 14 * 60 + 30)).toBe('2h 14m')
    expect(formatRemaining(3 * 3600)).toBe('3h')
    expect(formatRemaining(14 * 60)).toBe('14m')
    expect(formatRemaining(42)).toBe('under a minute')
  })

  it('secondsUntil uses the server clock offset, not the client clock', () => {
    // Client clock is 10 minutes slow relative to the server.
    const offset = 600
    const nextFreeAt = NOW_S + 3600
    // Client thinks it is NOW_S; server is at NOW_S + 600 → 50 min remaining.
    expect(secondsUntil(nextFreeAt, offset, NOW_MS)).toBe(3000)
    expect(secondsUntil(null, offset, NOW_MS)).toBeNull()
    // Never negative.
    expect(secondsUntil(NOW_S - 100, 0, NOW_MS)).toBe(0)
  })
})

describe('MamBlockedBanner (blocked-only, sitewide)', () => {
  afterEach(() => {
    vi.mocked(getMamStatus).mockReset()
  })

  it('renders nothing in the normal and warning states', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(status({ unsatisfied: 140, slotsFree: 5 }))
    renderWithProvider(<MamBlockedBanner />)
    await waitFor(() => expect(getMamStatus).toHaveBeenCalled())
    await act(async () => {})
    expect(screen.queryByTestId('mam-banner')).not.toBeInTheDocument()
  })

  it('shows the red banner with a countdown when blocked', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(
      status({ unsatisfied: 150, slotsFree: 0, blocked: true, nextFreeAt: Date.now() / 1000 + 2 * 3600 + 14 * 60, serverTime: Date.now() / 1000 })
    )
    renderWithProvider(<MamBlockedBanner />)
    const banner = await screen.findByTestId('mam-banner')
    expect(banner).toHaveTextContent('MAM download limit reached (150/150 unsatisfied)')
    expect(banner).toHaveTextContent('24-hour account block')
    expect(banner).toHaveTextContent('Next slot frees in 2h 14m')
  })

  it('says "waiting for current downloads" when next_free_at is null', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(status({ unsatisfied: 150, slotsFree: 0, blocked: true, nextFreeAt: null }))
    renderWithProvider(<MamBlockedBanner />)
    const banner = await screen.findByTestId('mam-banner')
    expect(banner).toHaveTextContent('Waiting for current downloads to finish')
  })

  it('shows the unverifiable variant when rTorrent is unreachable', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(status({ unsatisfied: null, slotsFree: null, blocked: true, nextFreeAt: null }))
    renderWithProvider(<MamBlockedBanner />)
    const banner = await screen.findByTestId('mam-banner')
    expect(banner).toHaveTextContent('MAM slot status unavailable')
    expect(banner).toHaveTextContent('usenet downloads are unaffected')
  })

  it('is mounted by PortalHeader so every page gets it, with no pill in the normal state', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(status({ unsatisfied: 150, slotsFree: 0, blocked: true }))
    const { unmount } = renderWithProvider(<PortalHeader title="Admin" showAdmin={false} onSignOut={() => {}} />)
    await screen.findByTestId('mam-banner')
    unmount()

    vi.mocked(getMamStatus).mockResolvedValue(status())
    renderWithProvider(<PortalHeader title="Admin" showAdmin={false} onSignOut={() => {}} />)
    await waitFor(() => expect(getMamStatus).toHaveBeenCalledTimes(2))
    await act(async () => {})
    expect(screen.queryByTestId('mam-banner')).not.toBeInTheDocument()
    expect(screen.queryByText(/MAM slots/)).not.toBeInTheDocument()
  })
})

describe('MAM slots card on the admin Status tab', () => {
  afterEach(() => {
    vi.mocked(getMamStatus).mockReset()
  })

  function renderPanel() {
    return renderWithProvider(
      <HistoryPanel items={[]} seeding={[]} statFilter="all" mediaFilter="all" onStatFilterChange={() => {}} onMediaFilterChange={() => {}} />
    )
  }

  it('shows free slots and usage in the normal state', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(status())
    renderPanel()
    const card = await screen.findByTestId('mam-slots-card')
    await waitFor(() => expect(card).toHaveTextContent('45'))
    expect(card).toHaveTextContent('MAM SLOTS')
    expect(card).toHaveTextContent('100/150 used')
    expect(card.querySelector('.metric-card__value')).toHaveClass('metric-card__value--teal')
    // First in the row
    expect(card.parentElement?.firstElementChild).toBe(card)
  })

  it('re-polls on the interval', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      vi.mocked(getMamStatus).mockResolvedValue(status())
      renderPanel()
      await screen.findByTestId('mam-slots-card')
      await waitFor(() => expect(getMamStatus).toHaveBeenCalledTimes(1))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(MAM_POLL_INTERVAL_MS + 50)
      })
      expect(getMamStatus).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('counts down against the server clock while blocked', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(NOW_MS)
    try {
      vi.mocked(getMamStatus).mockImplementation(async () =>
        status({ unsatisfied: 150, slotsFree: 0, blocked: true, nextFreeAt: NOW_S + 2 * 3600 + 14 * 60, serverTime: Date.now() / 1000 })
      )
      renderPanel()
      await screen.findByText(/2h 14m/)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3 * 60 * 1000)
      })
      expect(screen.getByTestId('mam-slots-card')).toHaveTextContent('2h 11m')
    } finally {
      vi.useRealTimers()
    }
  })

  it('shows the unverifiable state when rTorrent is unreachable (fail closed)', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(status({ unsatisfied: null, slotsFree: null, blocked: true, nextFreeAt: null }))
    renderPanel()
    const card = await screen.findByTestId('mam-slots-card')
    await waitFor(() => expect(card).toHaveTextContent('rTorrent unreachable'))
  })

  it('goes amber when low and red with a countdown when blocked', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(status({ unsatisfied: 140, slotsFree: 5 }))
    const { unmount } = renderPanel()
    await waitFor(() =>
      expect(screen.getByTestId('mam-slots-card').querySelector('.metric-card__value')).toHaveClass('metric-card__value--warning')
    )
    unmount()

    vi.mocked(getMamStatus).mockResolvedValue(
      status({ unsatisfied: 150, slotsFree: 0, blocked: true, nextFreeAt: Date.now() / 1000 + 2 * 3600 + 14 * 60, serverTime: Date.now() / 1000 })
    )
    renderPanel()
    const card = await screen.findByTestId('mam-slots-card')
    await waitFor(() => expect(card.querySelector('.metric-card__value')).toHaveClass('metric-card__value--error'))
    expect(card).toHaveTextContent('150/150 · next slot in 2h 14m')
  })
})

describe('ReleaseCard under MAM block', () => {
  afterEach(() => {
    vi.mocked(getMamStatus).mockReset()
  })

  it('disables torrent Download buttons but leaves usenet enabled', async () => {
    vi.mocked(getMamStatus).mockResolvedValue(
      status({ unsatisfied: 150, slotsFree: 0, blocked: true })
    )
    const onDownload = vi.fn()
    renderWithProvider(
      <>
        <ReleaseCard release={torrentRelease} viewMode="simple" downloading={false} onDownload={onDownload} />
        <ReleaseCard
          release={{ ...torrentRelease, guid: 'u1', protocol: 'usenet', indexer: 'NZBgeek' }}
          viewMode="simple"
          downloading={false}
          onDownload={onDownload}
        />
      </>
    )

    await waitFor(() => {
      const [torrentBtn, usenetBtn] = screen.getAllByRole('button', { name: 'Download' })
      expect(torrentBtn).toBeDisabled()
      expect(torrentBtn).toHaveAttribute('title', expect.stringContaining('MAM download limit reached'))
      expect(torrentBtn).not.toHaveAttribute('title', expect.stringContaining('notice above'))
      expect(usenetBtn).toBeEnabled()
    })
  })

  it('leaves buttons enabled with no provider (safe default)', () => {
    render(
      <ReleaseCard release={torrentRelease} viewMode="simple" downloading={false} onDownload={vi.fn()} />
    )
    expect(screen.getByRole('button', { name: 'Download' })).toBeEnabled()
  })
})

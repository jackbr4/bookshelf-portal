import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { ImportResolveStatus, ReleasesResponse } from '../lib/types'

vi.mock('../lib/api', async importOriginal => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    extractList: vi.fn(),
    startResolve: vi.fn(),
    getResolveStatus: vi.fn(),
    cancelResolve: vi.fn(async () => undefined),
    downloadRelease: vi.fn(),
    getMamStatus: vi.fn(async () => ({
      unsatisfied: 10, limit: 150, blockThreshold: 145, slotsFree: 135,
      blocked: false, nextFreeAt: null, serverTime: Date.now() / 1000,
    })),
    logout: vi.fn(),
  }
})

vi.mock('../lib/session', () => ({
  saveSession: vi.fn(),
  clearSession: vi.fn(),
  isSessionValid: vi.fn(() => true),
}))

import { ApiError, extractList, startResolve, getResolveStatus, cancelResolve, downloadRelease, getMamStatus } from '../lib/api'
import ImportRoute, { RESOLVE_POLL_MS } from '../routes/ImportRoute'
import { MamStatusProvider } from '../lib/mamStatus'

const EMPTY: ReleasesResponse = { ebookAccepted: [], ebookRejected: [], audiobookAccepted: [], audiobookRejected: [] }

const release = {
  guid: 'r1',
  title: 'Piranesi [EPUB]',
  indexer: 'MyAnonamouse',
  protocol: 'torrent',
  sizeMb: 1.2,
  detectedFormat: 'EPUB',
  seeders: 42,
  ageDays: 10,
  downloadUrl: 'http://localhost:29254/r1',
  score: 70,
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={['/import']}>
      <MamStatusProvider>
        <ImportRoute />
      </MamStatusProvider>
    </MemoryRouter>
  )
}

async function goToReview(books = [
  { title: 'Piranesi', author: 'Susanna Clarke', confidence: 'high' as const },
  { title: 'Stoner', author: '', confidence: 'low' as const },
]) {
  vi.mocked(extractList).mockResolvedValue({ books, source: 'url', sourceTitle: 'Best books' })
  renderRoute()
  await userEvent.type(screen.getByLabelText('Article URL'), 'https://example.com/list')
  fireEvent.click(screen.getByRole('button', { name: 'Extract books' }))
  await screen.findByTestId('import-review')
}

describe('ImportRoute — input stage', () => {
  afterEach(() => vi.clearAllMocks())

  it('requires something to submit', async () => {
    renderRoute()
    fireEvent.click(screen.getByRole('button', { name: 'Extract books' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a URL')
    expect(extractList).not.toHaveBeenCalled()
  })

  it('submits a URL and moves to review with the source title', async () => {
    await goToReview()
    expect(extractList).toHaveBeenCalledWith({ url: 'https://example.com/list' })
    expect(screen.getByTestId('import-review')).toHaveTextContent('Best books')
    expect(screen.getAllByTestId('review-row')).toHaveLength(2)
    expect(screen.getAllByTestId('confidence-low')).toHaveLength(1)
  })

  it('switches to the paste tab and submits text', async () => {
    vi.mocked(extractList).mockResolvedValue({ books: [], source: 'text', sourceTitle: null })
    renderRoute()
    fireEvent.click(screen.getByRole('tab', { name: 'Paste text' }))
    await userEvent.type(screen.getByLabelText('Article text'), 'Some article about books')
    fireEvent.click(screen.getByRole('button', { name: 'Extract books' }))
    await screen.findByTestId('import-review')
    expect(extractList).toHaveBeenCalledWith({ text: 'Some article about books' })
    expect(screen.getByTestId('import-review')).toHaveTextContent('No books in the list')
  })

  it('offers the paste tab when the URL fetch fails', async () => {
    vi.mocked(extractList).mockRejectedValue(
      new ApiError(422, 'The page returned HTTP 403', { code: 'fetch_failed', message: 'The page returned HTTP 403' })
    )
    renderRoute()
    await userEvent.type(screen.getByLabelText('Article URL'), 'https://example.com/paywall')
    fireEvent.click(screen.getByRole('button', { name: 'Extract books' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The page returned HTTP 403')
    fireEvent.click(within(alert).getByRole('button', { name: 'Paste the text instead' }))
    expect(screen.getByRole('tab', { name: 'Paste text' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('Article text')).toBeInTheDocument()
  })

  it('does not offer the paste tab for a configuration error', async () => {
    vi.mocked(extractList).mockRejectedValue(
      new ApiError(503, 'not configured', { code: 'not_configured', message: 'List import is not configured (no API key)' })
    )
    renderRoute()
    await userEvent.type(screen.getByLabelText('Article URL'), 'https://example.com/list')
    fireEvent.click(screen.getByRole('button', { name: 'Extract books' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('not configured')
    expect(within(alert).queryByRole('button')).toBeNull()
  })
})

describe('ImportRoute — review stage', () => {
  afterEach(() => vi.clearAllMocks())

  it('lets the user edit, remove and add rows, and counts usable books', async () => {
    await goToReview()
    expect(screen.getByRole('button', { name: 'Find availability (2)' })).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText('Author 2'))
    await userEvent.type(screen.getByLabelText('Author 2'), 'John Williams')
    fireEvent.click(screen.getByRole('button', { name: 'Remove Piranesi' }))
    expect(screen.getAllByTestId('review-row')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Find availability (1)' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '+ Add a book' }))
    expect(screen.getAllByTestId('review-row')).toHaveLength(2)
    // Blank row doesn't count
    expect(screen.getByRole('button', { name: 'Find availability (1)' })).toBeInTheDocument()

    vi.mocked(startResolve).mockResolvedValue({ jobId: 'j1', total: 1 })
    vi.mocked(getResolveStatus).mockResolvedValue({ jobId: 'j1', done: true, total: 1, completed: 1, results: [
      { index: 0, title: 'Stoner', author: 'John Williams', status: 'not_found', releases: EMPTY },
    ] })
    fireEvent.click(screen.getByRole('button', { name: 'Find availability (1)' }))
    await waitFor(() => expect(startResolve).toHaveBeenCalledWith([{ title: 'Stoner', author: 'John Williams' }]))
  })

  it('start over returns to the input stage', async () => {
    await goToReview()
    fireEvent.click(screen.getByRole('button', { name: 'Start over' }))
    expect(screen.getByTestId('import-input')).toBeInTheDocument()
  })
})

describe('ImportRoute — results stage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('polls the job, renders progressively, and downloads a release', async () => {
    await goToReview()
    vi.mocked(startResolve).mockResolvedValue({ jobId: 'j1', total: 2 })

    const partial: ImportResolveStatus = { jobId: 'j1', done: false, total: 2, completed: 1, results: [
      { index: 0, title: 'Piranesi', author: 'Susanna Clarke', status: 'available',
        releases: { ...EMPTY, ebookAccepted: [release] } },
      { index: 1, title: 'Stoner', author: '', status: 'pending' },
    ] }
    const full: ImportResolveStatus = { ...partial, done: true, completed: 2, results: [
      partial.results[0],
      { index: 1, title: 'Stoner', author: '', status: 'in_library', releases: { ...EMPTY, calibreTitle: 'Stoner' } },
    ] }
    vi.mocked(getResolveStatus).mockResolvedValueOnce(partial).mockResolvedValue(full)

    fireEvent.click(screen.getByRole('button', { name: 'Find availability (2)' }))
    await screen.findByTestId('import-results')

    // First poll result
    await waitFor(() => expect(screen.getByTestId('import-summary')).toHaveTextContent('Checking 1 of 2'))
    const cards = screen.getAllByTestId('import-book')
    expect(cards[0]).toHaveAttribute('data-status', 'available')
    expect(cards[1]).toHaveAttribute('data-status', 'pending')

    // Next poll → done
    await act(async () => {
      await vi.advanceTimersByTimeAsync(RESOLVE_POLL_MS + 50)
    })
    await waitFor(() => expect(screen.getByTestId('import-summary')).toHaveTextContent('1 available · 1 already in library'))
    expect(screen.getAllByTestId('import-book')[1]).toHaveTextContent('Already in Calibre: Stoner')

    // Polling stops once done
    const calls = vi.mocked(getResolveStatus).mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(RESOLVE_POLL_MS * 3)
    })
    expect(vi.mocked(getResolveStatus).mock.calls.length).toBe(calls)

    // Download the top ebook → uses the book's title/author, marks as sent
    vi.mocked(downloadRelease).mockResolvedValue({ ok: true, recordId: 'x', downloadId: 'y', message: 'Sent to rTorrent' })
    fireEvent.click(within(screen.getAllByTestId('import-book')[0]).getByRole('button', { name: 'Download' }))
    await waitFor(() => expect(downloadRelease).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Piranesi', author: 'Susanna Clarke', releaseTitle: 'Piranesi [EPUB]', mediaType: 'ebook',
    })))
    expect(await within(screen.getAllByTestId('import-book')[0]).findByText('✓ Sent')).toBeInTheDocument()
    expect(screen.getByRole('alert', { name: '' })).toHaveTextContent('Download started')
  })

  it('cancels the job when going back to the list', async () => {
    await goToReview()
    vi.mocked(startResolve).mockResolvedValue({ jobId: 'j2', total: 2 })
    vi.mocked(getResolveStatus).mockResolvedValue({ jobId: 'j2', done: false, total: 2, completed: 0, results: [
      { index: 0, title: 'Piranesi', author: 'Susanna Clarke', status: 'pending' },
      { index: 1, title: 'Stoner', author: '', status: 'pending' },
    ] })
    fireEvent.click(screen.getByRole('button', { name: 'Find availability (2)' }))
    await screen.findByTestId('import-results')
    fireEvent.click(screen.getByRole('button', { name: '← Edit list' }))
    expect(screen.getByTestId('import-review')).toBeInTheDocument()
    expect(cancelResolve).toHaveBeenCalledWith('j2')
    // The edited rows are preserved
    expect(screen.getAllByTestId('review-row')).toHaveLength(2)
  })

  it('marks pending books as errors if the job disappears', async () => {
    await goToReview()
    vi.mocked(startResolve).mockResolvedValue({ jobId: 'j3', total: 2 })
    vi.mocked(getResolveStatus).mockRejectedValue(new ApiError(404, 'Unknown or expired resolve job', 'Unknown or expired resolve job'))
    fireEvent.click(screen.getByRole('button', { name: 'Find availability (2)' }))
    await screen.findByTestId('import-results')
    await waitFor(() => {
      for (const card of screen.getAllByTestId('import-book')) {
        expect(card).toHaveAttribute('data-status', 'error')
      }
    })
    expect(screen.getByTestId('import-summary')).toHaveTextContent('2 failed')
  })
})

describe('ImportRoute — bulk download', () => {
  afterEach(() => vi.clearAllMocks())

  const usenetAudio = { ...release, guid: 'u1', title: 'Piranesi [M4B]', protocol: 'usenet', indexer: 'NZBgeek' }
  const stonerRelease = { ...release, guid: 'r2', title: 'Stoner [EPUB]' }

  async function goToDoneResults() {
    await goToReview()
    vi.mocked(startResolve).mockResolvedValue({ jobId: 'jb', total: 2 })
    vi.mocked(getResolveStatus).mockResolvedValue({ jobId: 'jb', done: true, total: 2, completed: 2, results: [
      { index: 0, title: 'Piranesi', author: 'Susanna Clarke', status: 'available',
        releases: { ...EMPTY, ebookAccepted: [release], audiobookAccepted: [usenetAudio] } },
      { index: 1, title: 'Stoner', author: '', status: 'available',
        releases: { ...EMPTY, ebookAccepted: [stonerRelease] } },
    ] })
    fireEvent.click(screen.getByRole('button', { name: 'Find availability (2)' }))
    await screen.findByTestId('import-bulk')
    await waitFor(() => expect(screen.getAllByRole('checkbox')).toHaveLength(3))
  }

  it('sends usenet always, torrents up to the fresh slot budget, and parks the rest', async () => {
    await goToDoneResults()
    // Only one torrent slot free right now
    vi.mocked(getMamStatus).mockResolvedValue({
      unsatisfied: 144, limit: 150, blockThreshold: 145, slotsFree: 1,
      blocked: false, nextFreeAt: Date.now() / 1000 + 3 * 3600, serverTime: Date.now() / 1000,
    })
    vi.mocked(downloadRelease).mockResolvedValue({ ok: true, recordId: 'x', downloadId: 'y', message: 'Sent' })

    fireEvent.click(screen.getByRole('button', { name: 'Select all ebooks' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select audiobook for Piranesi' }))
    expect(screen.getByRole('button', { name: 'Download selected (3)' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: 'Download selected (3)' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Download selected (1)' })).toBeInTheDocument())
    // Piranesi ebook (torrent, slot 1) + Piranesi audiobook (usenet, always) were sent, in list order
    expect(vi.mocked(downloadRelease).mock.calls.map(c => c[0].releaseTitle)).toEqual(['Piranesi [EPUB]', 'Piranesi [M4B]'])
    expect(screen.getAllByText('✓ Sent')).toHaveLength(2)
    // Stoner (torrent) is parked, still selected
    expect(screen.getByTestId('row-waiting')).toHaveTextContent('Waiting for slot')
    expect(screen.getByRole('checkbox', { name: 'Select ebook for Stoner' })).toBeChecked()
    expect(screen.getByRole('alert')).toHaveTextContent('Sent 2 downloads')
    expect(screen.getByRole('alert')).toHaveTextContent('1 waiting for a MAM slot')
  })

  it('parks every torrent when the slot status cannot be verified (fail closed)', async () => {
    await goToDoneResults()
    vi.mocked(getMamStatus).mockResolvedValue({
      unsatisfied: null, limit: 150, blockThreshold: 145, slotsFree: null,
      blocked: true, nextFreeAt: null, serverTime: Date.now() / 1000,
    })
    fireEvent.click(screen.getByRole('button', { name: 'Select all ebooks' }))
    fireEvent.click(screen.getByRole('button', { name: 'Download selected (2)' }))
    await waitFor(() => expect(screen.getAllByTestId('row-waiting')).toHaveLength(2))
    expect(downloadRelease).not.toHaveBeenCalled()
    // Both the sitewide banner and the toast are alerts here; check the toast.
    expect(document.querySelector('.portal-toast')).toHaveTextContent('Waiting for MAM slots')
    expect(screen.getByTestId('mam-banner')).toHaveTextContent('MAM slot status unavailable')
  })

  it('stops sending torrents after a 429 mid-run and marks the row waiting', async () => {
    await goToDoneResults()
    vi.mocked(getMamStatus).mockResolvedValue({
      unsatisfied: 100, limit: 150, blockThreshold: 145, slotsFree: 45,
      blocked: false, nextFreeAt: Date.now() / 1000 + 3600, serverTime: Date.now() / 1000,
    })
    vi.mocked(downloadRelease).mockRejectedValueOnce(
      new ApiError(429, 'paused', { message: 'paused', next_free_at: Date.now() / 1000 + 3600, unsatisfied: 150, limit: 150 })
    ).mockResolvedValue({ ok: true, recordId: 'x', downloadId: 'y', message: 'Sent' })

    fireEvent.click(screen.getByRole('button', { name: 'Select all ebooks' }))
    fireEvent.click(screen.getByRole('button', { name: 'Download selected (2)' }))
    await waitFor(() => expect(screen.getAllByTestId('row-waiting')).toHaveLength(2))
    // Only the first attempt hit the API; the second torrent was parked without trying
    expect(downloadRelease).toHaveBeenCalledTimes(1)
  })

  it('a single-row failure is reported inline and the rest still go', async () => {
    await goToDoneResults()
    vi.mocked(getMamStatus).mockResolvedValue({
      unsatisfied: 100, limit: 150, blockThreshold: 145, slotsFree: 45,
      blocked: false, nextFreeAt: null, serverTime: Date.now() / 1000,
    })
    vi.mocked(downloadRelease)
      .mockRejectedValueOnce(new ApiError(502, 'Dispatch failed: boom', 'Dispatch failed: boom'))
      .mockResolvedValue({ ok: true, recordId: 'x', downloadId: 'y', message: 'Sent' })

    fireEvent.click(screen.getByRole('button', { name: 'Select all ebooks' }))
    fireEvent.click(screen.getByRole('button', { name: 'Download selected (2)' }))
    await waitFor(() => expect(screen.getByTestId('row-failed')).toHaveTextContent('Failed: Dispatch failed: boom'))
    expect(screen.getAllByText('✓ Sent')).toHaveLength(1)
    expect(screen.getByRole('alert')).toHaveTextContent('1 sent · 1 failed')
  })
})

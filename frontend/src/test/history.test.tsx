import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describeHistory, relativeTime } from '../lib/historyText'
import ReleaseCard from '../components/ReleaseCard'
import ReleaseResults from '../components/ReleaseResults'
import ImportBookCard from '../components/ImportBookCard'
import type { ReleasesResponse } from '../lib/types'

vi.mock('../lib/api', () => ({
  getMamStatus: vi.fn(),
}))

const NOW = Date.parse('2026-09-02T12:00:00Z')

const release = {
  guid: 'r1',
  title: 'Dune [EPUB]',
  indexer: 'MyAnonamouse',
  protocol: 'torrent',
  sizeMb: 1.2,
  detectedFormat: 'EPUB',
  seeders: 42,
  ageDays: 10,
  downloadUrl: 'http://localhost:29254/r1',
  score: 70,
}

const EMPTY: ReleasesResponse = { ebookAccepted: [], ebookRejected: [], audiobookAccepted: [], audiobookRejected: [] }

describe('historyText', () => {
  it('relativeTime buckets sensibly', () => {
    const ago = (s: number) => new Date(NOW - s * 1000).toISOString()
    expect(relativeTime(ago(30), NOW)).toBe('just now')
    expect(relativeTime(ago(5 * 60), NOW)).toBe('5 minutes ago')
    expect(relativeTime(ago(3 * 3600), NOW)).toBe('3 hours ago')
    expect(relativeTime(ago(3 * 86400), NOW)).toBe('3 days ago')
    expect(relativeTime(ago(21 * 86400), NOW)).toBe('3 weeks ago')
    expect(relativeTime('garbage', NOW)).toBe('')
  })

  it('describeHistory builds the banner line', () => {
    expect(describeHistory({ status: 'downloading', createdAt: new Date(NOW - 3 * 86400 * 1000).toISOString(), mediaType: 'audiobook' }, NOW))
      .toBe('Requested 3 days ago · audiobook · still downloading')
    expect(describeHistory({ status: 'imported', createdAt: new Date(NOW - 3600 * 1000).toISOString(), mediaType: 'ebook' }, NOW))
      .toBe('Requested 1 hour ago · ebook · imported')
  })
})

describe('already-requested releases', () => {
  it('ReleaseCard swaps the button for a badge with an escape hatch', () => {
    const onDownload = vi.fn()
    render(<ReleaseCard release={{ ...release, alreadyRequested: true }} viewMode="simple" downloading={false} onDownload={onDownload} />)
    expect(screen.queryByRole('button', { name: 'Download' })).toBeNull()
    expect(screen.getByText('↻ Already requested')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Download anyway' }))
    expect(onDownload).toHaveBeenCalledWith(expect.objectContaining({ guid: 'r1' }))
  })

  it('ReleaseResults shows the history banner', () => {
    const results: ReleasesResponse = {
      ...EMPTY,
      ebookAccepted: [{ ...release, alreadyRequested: true }],
      historyMatch: { status: 'imported', createdAt: new Date(Date.now() - 2 * 86400 * 1000).toISOString(), releaseTitle: 'Dune [EPUB]', mediaType: 'ebook' },
    }
    render(<ReleaseResults results={results} searchTitle="Dune" searchAuthor="" onDownload={vi.fn()} />)
    expect(screen.getByTestId('history-banner')).toHaveTextContent('Requested 2 days ago · ebook · imported — Dune [EPUB]')
  })

  it('ImportBookCard renders the requested state with releases behind the expander', () => {
    const item = {
      index: 0, title: 'Dune', author: 'Frank Herbert', status: 'requested' as const,
      releases: {
        ...EMPTY,
        ebookAccepted: [{ ...release, alreadyRequested: true }, { ...release, guid: 'r2', title: 'Dune [MOBI]' }],
        historyMatch: { status: 'downloading', createdAt: new Date(Date.now() - 3 * 86400 * 1000).toISOString(), releaseTitle: 'Dune [EPUB]', mediaType: 'ebook' },
      },
    }
    render(
      <MemoryRouter>
        <ImportBookCard item={item} downloadingGuid={null} sentGuids={new Set()} onDownload={vi.fn()} />
      </MemoryRouter>
    )
    expect(screen.getByTestId('import-book')).toHaveAttribute('data-status', 'requested')
    expect(screen.getByTestId('history-banner')).toHaveTextContent('Requested 3 days ago')
    // No download buttons until expanded
    expect(screen.queryByRole('button', { name: 'Download' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Show 2 releases anyway' }))
    // Only one banner (ReleaseResults' own), the previously-sent release is badged, the other is downloadable
    expect(screen.getAllByTestId('history-banner')).toHaveLength(1)
    expect(screen.getByText('↻ Already requested')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Download' })).toHaveLength(1)
  })
})

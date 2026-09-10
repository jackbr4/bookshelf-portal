import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import HistoryPanel from '../components/HistoryPanel'
import type { HistoryItem } from '../lib/types'

vi.mock('../lib/api', () => ({
  getMamStatus: vi.fn(),
}))

function makeItem(overrides: Partial<HistoryItem> = {}): HistoryItem {
  return {
    id: 'h1',
    title: 'Dune',
    author: 'Frank Herbert',
    status: 'imported',
    createdAt: '2026-09-01T00:00:00Z',
    updatedAt: '2026-09-01T00:00:00Z',
    mediaType: 'ebook',
    ...overrides,
  }
}

const noop = () => {}

describe('HistoryPanel "In Library" Calibre link', () => {
  it('shows a "View in Calibre" link when the item has a libraryUrl', () => {
    render(
      <HistoryPanel
        items={[makeItem({ libraryUrl: 'https://library.example.com/book/42' })]}
        seeding={[]}
        statFilter="all"
        mediaFilter="all"
        onStatFilterChange={noop}
        onMediaFilterChange={noop}
      />
    )
    const link = screen.getByRole('link', { name: 'View in Calibre →' })
    expect(link).toHaveAttribute('href', 'https://library.example.com/book/42')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('omits the link when the item has no libraryUrl', () => {
    render(
      <HistoryPanel
        items={[makeItem({ libraryUrl: null })]}
        seeding={[]}
        statFilter="all"
        mediaFilter="all"
        onStatFilterChange={noop}
        onMediaFilterChange={noop}
      />
    )
    expect(screen.queryByRole('link', { name: 'View in Calibre →' })).not.toBeInTheDocument()
  })
})

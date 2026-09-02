import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import PasswordGate from '../components/PasswordGate'
import SearchCard from '../components/SearchCard'
import ReleaseCard from '../components/ReleaseCard'

vi.mock('../lib/api', () => ({
  login: vi.fn(),
  getReleases: vi.fn(),
  downloadRelease: vi.fn(),
  logout: vi.fn(),
  getHistory: vi.fn(),
  getSeeding: vi.fn(),
  getGoodreadsProfiles: vi.fn(),
  addGoodreadsProfile: vi.fn(),
  deleteGoodreadsProfile: vi.fn(),
  getMamStatus: vi.fn(),
  mamBlockedDetail: vi.fn(() => null),
}))

vi.mock('../lib/session', () => ({
  saveSession: vi.fn(),
  clearSession: vi.fn(),
  isSessionValid: vi.fn(() => false),
}))

import { login } from '../lib/api'

const sampleRelease = {
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

describe('PasswordGate', () => {
  it('shows error on empty submit', async () => {
    const onSuccess = vi.fn()
    render(<PasswordGate onSuccess={onSuccess} />)
    fireEvent.click(screen.getByText('Continue'))
    await waitFor(() => {
      expect(screen.getByText('Please enter the access code.')).toBeInTheDocument()
    })
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it('calls onSuccess with correct password', async () => {
    const mockLogin = vi.mocked(login)
    mockLogin.mockResolvedValue({ ok: true, expiresAt: new Date(Date.now() + 3600000).toISOString() })
    const onSuccess = vi.fn()
    render(<PasswordGate onSuccess={onSuccess} />)
    await userEvent.type(screen.getByPlaceholderText('Enter access code'), 'family')
    fireEvent.click(screen.getByText('Continue'))
    await waitFor(() => expect(onSuccess).toHaveBeenCalled())
  })
})

describe('SearchCard', () => {
  it('shows inline validation on empty search', async () => {
    const onSearch = vi.fn()
    render(
      <SearchCard
        title=""
        author=""
        onTitleChange={vi.fn()}
        onAuthorChange={vi.fn()}
        onSearch={onSearch}
        loading={false}
      />
    )
    fireEvent.click(screen.getByText('Search'))
    await waitFor(() => {
      expect(screen.getByText('Enter a title and/or author to search.')).toBeInTheDocument()
    })
    expect(onSearch).not.toHaveBeenCalled()
  })

  it('calls onSearch when title is provided', async () => {
    const onSearch = vi.fn()
    render(
      <SearchCard
        title="Dune"
        author=""
        onTitleChange={vi.fn()}
        onAuthorChange={vi.fn()}
        onSearch={onSearch}
        loading={false}
      />
    )
    fireEvent.click(screen.getByText('Search'))
    expect(onSearch).toHaveBeenCalled()
  })
})

describe('ReleaseCard', () => {
  it('renders download button', () => {
    render(
      <ReleaseCard
        release={sampleRelease}
        viewMode="simple"
        downloading={false}
        onDownload={vi.fn()}
      />
    )
    expect(screen.getByText('Download')).not.toBeDisabled()
    expect(screen.getByText(sampleRelease.title)).toBeInTheDocument()
  })
})

describe('PortalHeader', () => {
  it('renders admin link on request page', async () => {
    const PortalHeader = (await import('../components/PortalHeader')).default
    render(
      <MemoryRouter>
        <PortalHeader title="Book Request Portal" onSignOut={vi.fn()} />
      </MemoryRouter>
    )
    expect(screen.getByText('Admin')).toBeInTheDocument()
    expect(screen.getByText('Sign out')).toBeInTheDocument()
  })
})

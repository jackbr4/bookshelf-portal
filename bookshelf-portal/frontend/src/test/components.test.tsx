import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PasswordGate from '../components/PasswordGate'
import SearchPanel from '../components/SearchPanel'
import ResultCard from '../components/ResultCard'
import StatusBadge from '../components/StatusBadge'

// Mock API
vi.mock('../lib/api', () => ({
  login: vi.fn(),
  search: vi.fn(),
  addBook: vi.fn(),
  addSeries: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('../lib/session', () => ({
  saveSession: vi.fn(),
  clearSession: vi.fn(),
  isSessionValid: vi.fn(() => false),
}))

import { login } from '../lib/api'

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

  it('shows error on incorrect password', async () => {
    const mockLogin = vi.mocked(login)
    mockLogin.mockResolvedValue({ ok: false })
    const onSuccess = vi.fn()
    render(<PasswordGate onSuccess={onSuccess} />)
    await userEvent.type(screen.getByPlaceholderText('Enter access code'), 'wrong')
    fireEvent.click(screen.getByText('Continue'))
    await waitFor(() => {
      expect(screen.getByText('Incorrect access code. Please try again.')).toBeInTheDocument()
    })
  })
})

describe('SearchPanel', () => {
  it('shows inline validation on empty search', async () => {
    const onSearch = vi.fn()
    render(<SearchPanel onSearch={onSearch} loading={false} />)
    fireEvent.click(screen.getByText('Search'))
    await waitFor(() => {
      expect(screen.getByText('Enter a book or series to search.')).toBeInTheDocument()
    })
    expect(onSearch).not.toHaveBeenCalled()
  })

  it('calls onSearch with query', async () => {
    const onSearch = vi.fn()
    render(<SearchPanel onSearch={onSearch} loading={false} />)
    await userEvent.type(screen.getByPlaceholderText('Search for a book or series'), 'Dune')
    fireEvent.click(screen.getByText('Search'))
    expect(onSearch).toHaveBeenCalledWith('Dune')
  })
})

describe('StatusBadge', () => {
  it('renders "Available" for available status', () => {
    render(<StatusBadge status="available" />)
    expect(screen.getByText('Available')).toBeInTheDocument()
  })

  it('renders "Already in library" for already_in_library status', () => {
    render(<StatusBadge status="already_in_library" />)
    expect(screen.getByText('Already in library')).toBeInTheDocument()
  })
})

describe('ResultCard', () => {
  it('disables button for duplicate book', () => {
    const item = { id: 'b1', title: 'Dune', author: 'Frank Herbert', status: 'already_in_library' as const }
    render(<ResultCard kind="book" item={item} onAdd={vi.fn()} />)
    expect(screen.getByText('Already Added')).toBeDisabled()
  })

  it('enables Add Book button when available', () => {
    const item = { id: 'b1', title: 'Dune', author: 'Frank Herbert', status: 'available' as const }
    render(<ResultCard kind="book" item={item} onAdd={vi.fn()} />)
    expect(screen.getByText('Add Book')).not.toBeDisabled()
  })
})

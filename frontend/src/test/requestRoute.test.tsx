import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../lib/api', async importOriginal => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return { ...actual, getReleases: vi.fn(), logout: vi.fn() }
})

vi.mock('../lib/session', () => ({
  saveSession: vi.fn(),
  clearSession: vi.fn(),
  isSessionValid: vi.fn(() => true),
}))

import RequestRoute from '../routes/RequestRoute'

function renderWithRouting() {
  return render(
    <MemoryRouter initialEntries={['/request']}>
      <Routes>
        <Route path="/request" element={<RequestRoute />} />
        <Route path="/import" element={<div data-testid="landed-on-import" />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('RequestRoute — search/import mode tabs', () => {
  afterEach(() => vi.clearAllMocks())

  it('defaults to the "One book" tab, matching the pre-unification search form', () => {
    renderWithRouting()
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
    expect(screen.getByLabelText('Author')).toBeInTheDocument()
    expect(screen.queryByLabelText('Article URL')).not.toBeInTheDocument()
  })

  it('submitting a URL navigates to /import carrying the input, without calling getReleases', async () => {
    renderWithRouting()
    fireEvent.click(screen.getByRole('tab', { name: 'From a URL' }))
    await userEvent.type(screen.getByLabelText('Article URL'), 'https://example.com/list')
    fireEvent.click(screen.getByRole('button', { name: 'Extract books' }))
    expect(await screen.findByTestId('landed-on-import')).toBeInTheDocument()
  })

  it('submitting pasted text navigates to /import carrying the text', async () => {
    renderWithRouting()
    fireEvent.click(screen.getByRole('tab', { name: 'Paste text' }))
    await userEvent.type(screen.getByLabelText('Article text'), 'a list of books')
    fireEvent.click(screen.getByRole('button', { name: 'Extract books' }))
    expect(await screen.findByTestId('landed-on-import')).toBeInTheDocument()
  })
})

import { useState } from 'react'
import PortalInput from './PortalInput'
import PortalButton from './PortalButton'

interface Props {
  onSearch: (query: string) => void
  loading: boolean
}

export default function SearchPanel({ onSearch, loading }: Props) {
  const [query, setQuery] = useState('')
  const [validationError, setValidationError] = useState('')

  function handleSearch() {
    if (!query.trim()) {
      setValidationError('Enter a book or series to search.')
      return
    }
    setValidationError('')
    onSearch(query.trim())
  }

  return (
    <div>
      <p className="text-muted mb-3" style={{ fontSize: '14px' }}>
        Search for a book below to be added to Calibre. For best results, please provide the full title and author name separated by a comma.
      </p>
      <div className="d-flex gap-2">
        <div className="flex-grow-1">
          <PortalInput
            id="search-query"
            placeholder="Search for a book"
            value={query}
            onChange={(v) => { setQuery(v); if (validationError) setValidationError('') }}
            onEnter={handleSearch}
            state={validationError ? 'error' : 'default'}
            helperText={validationError || undefined}
          />
        </div>
        <div>
          <PortalButton
            variant="primary"
            loading={loading}
            onClick={handleSearch}
            style={{ whiteSpace: 'nowrap', height: '38px' }}
          >
            {loading ? 'Searching\u2026' : 'Search'}
          </PortalButton>
        </div>
      </div>
      <p className="text-muted mt-2 mb-0" style={{ fontSize: '13px' }}>
        Search results may take 10–20 seconds to appear.
      </p>
    </div>
  )
}

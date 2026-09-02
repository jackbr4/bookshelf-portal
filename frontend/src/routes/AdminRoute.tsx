import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PortalHeader from '../components/PortalHeader'
import HistoryPanel from '../components/HistoryPanel'
import GoodreadsPanel from '../components/GoodreadsPanel'
import { getHistory, getSeeding, getGoodreadsProfiles, logout } from '../lib/api'
import { clearSession } from '../lib/session'
import type { HistoryItem, SeedingItem, GoodreadsProfile, MediaFilter, StatFilter } from '../lib/types'

type AdminTab = 'history' | 'goodreads'

export default function AdminRoute() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<AdminTab>('history')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [seeding, setSeeding] = useState<SeedingItem[]>([])
  const [profiles, setProfiles] = useState<GoodreadsProfile[]>([])
  const [statFilter, setStatFilter] = useState<StatFilter>('all')
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [historyItems, seedingItems, profileItems] = await Promise.all([
        getHistory(),
        getSeeding(),
        getGoodreadsProfiles(),
      ])
      setHistory(historyItems)
      setSeeding(seedingItems)
      setProfiles(profileItems)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg === 'SESSION_EXPIRED') {
        clearSession()
        navigate('/', { replace: true })
        return
      }
      setError(msg || 'Failed to load admin data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  async function handleLogout() {
    await logout()
    clearSession()
    navigate('/', { replace: true })
  }

  return (
    <div className="portal-page">
      <PortalHeader
        title="Admin"
        showAdmin={false}
        backLink={{ to: '/request', label: '← back to requests' }}
        onSignOut={handleLogout}
      />

      <main className="portal-main portal-main--admin">
        <div className="admin-tabs">
          <button
            type="button"
            className={`admin-tab ${tab === 'history' ? 'admin-tab--active' : ''}`}
            onClick={() => setTab('history')}
          >
            Status
          </button>
          <button
            type="button"
            className={`admin-tab ${tab === 'goodreads' ? 'admin-tab--active' : ''}`}
            onClick={() => setTab('goodreads')}
          >
            Goodreads Profiles
          </button>
        </div>

        {loading && <p style={{ color: 'var(--color-text-secondary)' }}>Loading…</p>}
        {error && <p className="field-error" role="alert">{error}</p>}

        {!loading && !error && tab === 'history' && (
          <HistoryPanel
            items={history}
            seeding={seeding}
            statFilter={statFilter}
            mediaFilter={mediaFilter}
            onStatFilterChange={setStatFilter}
            onMediaFilterChange={setMediaFilter}
          />
        )}

        {!loading && !error && tab === 'goodreads' && (
          <GoodreadsPanel profiles={profiles} onChange={loadData} />
        )}
      </main>
    </div>
  )
}

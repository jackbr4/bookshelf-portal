import { useState } from 'react'
import type { GoodreadsProfile } from '../lib/types'
import PortalButton from './PortalButton'
import { addGoodreadsProfile, deleteGoodreadsProfile } from '../lib/api'

interface Props {
  profiles: GoodreadsProfile[]
  onChange: () => Promise<void>
}

function syncModeLabel(profile: GoodreadsProfile): string {
  if (!profile.sync_from) return 'Full shelf'
  return `New additions from ${profile.sync_from}`
}

export default function GoodreadsPanel({ profiles, onChange }: Props) {
  const [name, setName] = useState('')
  const [userId, setUserId] = useState('')
  const [shelf, setShelf] = useState('to-read')
  const [fullShelf, setFullShelf] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleAdd() {
    if (!name.trim() || !userId.trim()) {
      setError('Enter a first name and Goodreads user ID.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await addGoodreadsProfile({
        name: name.trim(),
        user_id: userId.trim(),
        shelf: shelf.trim() || 'to-read',
        sync_from: fullShelf ? null : new Date().toISOString().slice(0, 10),
      })
      setName('')
      setUserId('')
      setShelf('to-read')
      setFullShelf(false)
      await onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add profile.')
    } finally {
      setLoading(false)
    }
  }

  async function handleRemove(profileId: string) {
    setLoading(true)
    try {
      await deleteGoodreadsProfile(profileId)
      await onChange()
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <p className="section-eyebrow">{profiles.length} PROFILES</p>

      <div className="goodreads-list">
        {profiles.map(profile => (
          <article key={profile.id} className="profile-card">
            <div>
              <h3 className="profile-card__name">{profile.name}</h3>
              <p className="profile-card__meta">
                ID: {profile.user_id} · Shelf: {profile.shelf} · {syncModeLabel(profile)}
              </p>
            </div>
            <PortalButton variant="ghost" size="sm" disabled={loading} onClick={() => handleRemove(profile.id)}>
              Remove
            </PortalButton>
          </article>
        ))}
      </div>

      <div className="add-profile-card">
        <h3 style={{ margin: '0 0 8px', fontSize: 16, fontWeight: 800 }}>Add a profile</h3>
        <p style={{ margin: 0, fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Enter a first name and a Goodreads user ID. To find your user ID, go to your Goodreads profile page — the URL will look like goodreads.com/user/show/12345678-firstname
        </p>

        <div className="add-profile-card__grid">
          <div>
            <label className="field-label" htmlFor="profile-name">First name</label>
            <input id="profile-name" className="field-input" placeholder="e.g. Sarah" value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="profile-user-id">Goodreads user ID</label>
            <input id="profile-user-id" className="field-input" placeholder="e.g. 98765432-sarah" value={userId} onChange={e => setUserId(e.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="profile-shelf">Shelf</label>
            <input id="profile-shelf" className="field-input" value={shelf} onChange={e => setShelf(e.target.value)} />
          </div>
        </div>

        <label className="checkbox-row">
          <input type="checkbox" checked={fullShelf} onChange={e => setFullShelf(e.target.checked)} />
          <span>Download all books from my Want to Read shelf</span>
        </label>

        {error && <p className="field-error">{error}</p>}

        <PortalButton variant="primary" size="sm" loading={loading} onClick={handleAdd} style={{ marginTop: 14 }}>
          Add profile
        </PortalButton>
      </div>
    </section>
  )
}

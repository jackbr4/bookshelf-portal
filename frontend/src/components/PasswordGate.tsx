import { useState } from 'react'
import { login } from '../lib/api'
import { saveSession } from '../lib/session'
import PortalButton from './PortalButton'

interface Props {
  onSuccess: () => void
}

export default function PasswordGate({ onSuccess }: Props) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit() {
    if (!code.trim()) {
      setError('Please enter the access code.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await login(code.trim())
      if (res.ok && res.expiresAt) {
        saveSession(res.expiresAt)
        onSuccess()
      } else {
        setError('Incorrect access code. Please try again.')
      }
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="portal-gate-card">
      <div className="text-center mb-4">
        <div style={{ fontSize: '2.5rem' }}>📚</div>
        <h2 className="portal-topbar__title" style={{ fontSize: '20px', marginTop: 12 }}>Book Request Portal</h2>
        <p style={{ margin: '8px 0 0', fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Enter the access code to continue
        </p>
      </div>

      <label className="field-label" htmlFor="access-code">Access Code</label>
      <input
        id="access-code"
        className="field-input"
        type="password"
        placeholder="Enter access code"
        value={code}
        onChange={e => setCode(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && handleSubmit()}
      />

      {error && (
        <div className="field-error" role="alert">{error}</div>
      )}

      <PortalButton
        variant="primary"
        className="w-100"
        style={{ width: '100%', marginTop: 16 }}
        loading={loading}
        onClick={handleSubmit}
      >
        Continue
      </PortalButton>
    </div>
  )
}

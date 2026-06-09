import { useState } from 'react'
import { login } from '../lib/api'
import { saveSession } from '../lib/session'
import PortalInput from './PortalInput'
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
      <div className="card shadow-sm border-0">
        <div className="card-body p-4 p-sm-5">
          <div className="text-center mb-4">
            <div style={{ fontSize: '2.5rem' }}>📚</div>
            <h2 className="h4 mt-2 mb-1 fw-semibold">Book Request Portal</h2>
            <p className="text-muted mb-0" style={{ fontSize: '14px' }}>
              Enter the access code to continue
            </p>
          </div>

          <PortalInput
            id="access-code"
            label="Access Code"
            type="password"
            placeholder="Enter access code"
            value={code}
            onChange={setCode}
            onEnter={handleSubmit}
            state={error ? 'error' : 'default'}
          />

          {error && (
            <div className="text-danger mt-2" style={{ fontSize: '13px' }} role="alert">
              {error}
            </div>
          )}

          <PortalButton
            variant="primary"
            className="w-100 mt-3"
            loading={loading}
            onClick={handleSubmit}
          >
            Continue
          </PortalButton>
        </div>
      </div>
    </div>
  )
}

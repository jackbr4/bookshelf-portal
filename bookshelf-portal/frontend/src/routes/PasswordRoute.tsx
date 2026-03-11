import { useNavigate } from 'react-router-dom'
import { isSessionValid } from '../lib/session'
import PasswordGate from '../components/PasswordGate'
import { useEffect } from 'react'

export default function PasswordRoute() {
  const navigate = useNavigate()

  useEffect(() => {
    if (isSessionValid()) {
      navigate('/request', { replace: true })
    }
  }, [navigate])

  return (
    <div className="min-vh-100 d-flex align-items-center justify-content-center p-3" style={{ background: 'var(--color-page-bg)' }}>
      <PasswordGate onSuccess={() => navigate('/request', { replace: true })} />
    </div>
  )
}

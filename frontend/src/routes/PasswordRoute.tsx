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
    <div className="portal-gate-wrap">
      <PasswordGate onSuccess={() => navigate('/request', { replace: true })} />
    </div>
  )
}

import { Link } from 'react-router-dom'
import PortalButton from './PortalButton'
import { MamBlockedBanner, MamStatusPill } from './MamStatusBanner'

interface Props {
  title: string
  showAdmin?: boolean
  showImport?: boolean
  backLink?: { to: string; label: string }
  onSignOut: () => void
}

export default function PortalHeader({ title, showAdmin = true, showImport = true, backLink, onSignOut }: Props) {
  return (
    <>
      <header className="portal-topbar">
        <div>
          <h1 className="portal-topbar__title">{title}</h1>
          {backLink && (
            <Link to={backLink.to} style={{ fontSize: '15px', fontWeight: 700, color: 'var(--color-text-secondary)', textDecoration: 'none' }}>
              {backLink.label}
            </Link>
          )}
        </div>
        <div className="portal-topbar__actions">
          <MamStatusPill />
          {showImport && (
            <Link to="/import" style={{ textDecoration: 'none' }}>
              <PortalButton variant="soft" size="sm" type="button">Import list</PortalButton>
            </Link>
          )}
          {showAdmin && (
            <Link to="/admin" style={{ textDecoration: 'none' }}>
              <PortalButton variant="soft" size="sm" type="button">Admin</PortalButton>
            </Link>
          )}
          <PortalButton variant="ghost" size="sm" type="button" onClick={onSignOut}>
            Sign out
          </PortalButton>
        </div>
      </header>
      <MamBlockedBanner />
    </>
  )
}

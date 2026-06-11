import type { ToastState } from '../lib/types'

interface Props extends ToastState {
  onDismiss: () => void
}

export default function PortalToast({ kind, message, subMessage, actionLabel, onAction, onDismiss }: Props) {
  return (
    <div className="portal-toast-container">
      <div className={`portal-toast portal-toast--${kind}`} role="alert" aria-live="assertive">
        <div style={{ flex: 1 }}>
          <p style={{ margin: 0, fontWeight: 800, fontSize: 14 }}>{message}</p>
          {subMessage && (
            <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-text-secondary)' }}>{subMessage}</p>
          )}
          {actionLabel && onAction && (
            <button
              type="button"
              onClick={onAction}
              style={{
                marginTop: 8,
                background: 'none',
                border: 'none',
                color: 'var(--color-accent)',
                textDecoration: 'underline',
                cursor: 'pointer',
                padding: 0,
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              {actionLabel}
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--color-text-secondary)',
            cursor: 'pointer',
            padding: 0,
            fontSize: 18,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>
    </div>
  )
}

import type { ToastState } from '../lib/types'

interface Props extends ToastState {
  onDismiss: () => void
}

const STYLE_MAP = {
  success: {
    bg: '#D1E7DD',
    border: '#BADBCC',
    text: '#0F5132',
    icon: '✓',
  },
  info: {
    bg: '#CFF4FC',
    border: '#B6EFFB',
    text: '#055160',
    icon: 'ℹ',
  },
  error: {
    bg: '#F8D7DA',
    border: '#F5C2C7',
    text: '#842029',
    icon: '✕',
  },
}

export default function PortalToast({ kind, message, subMessage, actionLabel, onAction, onDismiss }: Props) {
  const s = STYLE_MAP[kind]

  return (
    <div className="portal-toast-container">
      <div
        role="alert"
        aria-live="assertive"
        style={{
          background: s.bg,
          border: `1px solid ${s.border}`,
          color: s.text,
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          gap: '10px',
          alignItems: 'flex-start',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        }}
      >
        <span style={{ fontSize: '16px', flexShrink: 0, marginTop: '1px' }}>{s.icon}</span>
        <div style={{ flex: 1 }}>
          <p style={{ margin: 0, fontWeight: 500, fontSize: '14px' }}>{message}</p>
          {subMessage && (
            <p style={{ margin: '2px 0 0', fontSize: '13px', opacity: 0.85 }}>{subMessage}</p>
          )}
          {actionLabel && onAction && (
            <button
              onClick={onAction}
              style={{
                marginTop: '6px',
                background: 'none',
                border: 'none',
                color: s.text,
                textDecoration: 'underline',
                cursor: 'pointer',
                padding: 0,
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              {actionLabel}
            </button>
          )}
        </div>
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            background: 'none',
            border: 'none',
            color: s.text,
            cursor: 'pointer',
            padding: '0 0 0 4px',
            fontSize: '16px',
            lineHeight: 1,
            opacity: 0.7,
            flexShrink: 0,
          }}
        >
          ×
        </button>
      </div>
    </div>
  )
}

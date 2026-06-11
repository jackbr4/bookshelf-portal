import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'soft' | 'ghost'
type Size = 'sm' | 'md'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: React.ReactNode
}

export default function PortalButton({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  children,
  className = '',
  ...rest
}: Props) {
  const isDisabled = disabled || loading

  return (
    <button
      className={`portal-btn portal-btn--${variant} portal-btn--${size} ${loading ? 'btn-loading' : ''} ${className}`}
      disabled={isDisabled}
      {...rest}
    >
      {loading && (
        <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
      )}
      {children}
    </button>
  )
}

import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'outline-primary' | 'outline-secondary' | 'success' | 'danger'
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
  const bsSize = size === 'sm' ? 'btn-sm' : ''
  const isDisabled = disabled || loading

  return (
    <button
      className={`btn btn-${variant} ${bsSize} ${loading ? 'btn-loading' : ''} ${className}`}
      disabled={isDisabled}
      {...rest}
    >
      {loading && (
        <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
      )}
      {children}
    </button>
  )
}

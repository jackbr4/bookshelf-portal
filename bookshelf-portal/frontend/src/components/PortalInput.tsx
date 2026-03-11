import { type ChangeEvent, type KeyboardEvent } from 'react'

interface Props {
  label?: string
  placeholder?: string
  value: string
  onChange: (v: string) => void
  onEnter?: () => void
  state?: 'default' | 'error'
  helperText?: string
  type?: 'text' | 'password'
  id?: string
}

export default function PortalInput({
  label,
  placeholder,
  value,
  onChange,
  onEnter,
  state = 'default',
  helperText,
  type = 'text',
  id = 'portal-input',
}: Props) {
  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && onEnter) onEnter()
  }

  return (
    <div>
      {label && (
        <label htmlFor={id} className="form-label fw-medium">
          {label}
        </label>
      )}
      <input
        id={id}
        type={type}
        className={`form-control ${state === 'error' ? 'is-invalid' : ''}`}
        placeholder={placeholder}
        value={value}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
        onKeyDown={handleKey}
        autoComplete={type === 'password' ? 'current-password' : 'off'}
      />
      {helperText && (
        <div className={state === 'error' ? 'invalid-feedback d-block' : 'form-text text-muted'}>
          {helperText}
        </div>
      )}
    </div>
  )
}

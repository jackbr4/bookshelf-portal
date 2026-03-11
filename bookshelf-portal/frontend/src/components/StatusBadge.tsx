import type { ItemStatus } from '../lib/types'

interface Props {
  status: ItemStatus
}

const CONFIG: Record<ItemStatus, { label: string; className: string }> = {
  available: { label: 'Available', className: 'badge-available' },
  already_in_library: { label: 'Already in library', className: 'badge-library' },
  already_monitored: { label: 'Already monitored', className: 'badge-monitored' },
}

export default function StatusBadge({ status }: Props) {
  const { label, className } = CONFIG[status]
  return (
    <span className={`badge rounded-pill fw-normal ${className}`} style={{ fontSize: '12px' }}>
      {label}
    </span>
  )
}

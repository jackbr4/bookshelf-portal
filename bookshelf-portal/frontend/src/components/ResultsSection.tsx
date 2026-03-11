import ResultCard from './ResultCard'
import type { BookResult, SeriesResult } from '../lib/types'

type Kind = 'book' | 'series'

interface Props {
  heading: string
  kind: Kind
  items: (BookResult | SeriesResult)[]
  onAdd: (item: BookResult | SeriesResult) => Promise<void>
}

export default function ResultsSection({ heading, kind, items, onAdd }: Props) {
  if (items.length === 0) return null

  return (
    <section>
      <h2 className="h6 fw-semibold text-muted text-uppercase mb-2" style={{ fontSize: '12px', letterSpacing: '0.05em' }}>
        {heading} <span className="text-muted fw-normal">({items.length})</span>
      </h2>
      <div className="d-flex flex-column gap-2">
        {items.map(item => (
          <ResultCard key={item.id} kind={kind} item={item} onAdd={onAdd} />
        ))}
      </div>
    </section>
  )
}

import { StatusPill } from './StatusPill'

export function Metric({ label, value, note, pill = false }: { label: string; value: string; note: string; pill?: boolean }) {
  return <article className="metric-card"><span>{label}</span><strong>{pill ? <StatusPill value={value} /> : value}</strong><small>{note}</small></article>
}

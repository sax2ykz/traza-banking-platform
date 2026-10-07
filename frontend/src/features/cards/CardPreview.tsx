import { StatusPill } from '../../components/ui/StatusPill'
import type { Card } from '../../types'

interface CardPreviewProps {
  card: Card
  expiry: string
  reference: string
  onOpen: () => void
}

export function CardPreview({ card, expiry, reference, onOpen }: CardPreviewProps) {
  return (
    <button
      className="bank-card card-preview"
      type="button"
      aria-label={`Ver detalle de la tarjeta terminada en ${card.last_four}`}
      aria-haspopup="dialog"
      aria-controls="card-details-dialog"
      onClick={onOpen}
    >
      <span className="bank-card-top">
        <span className="bank-card-brand">TRAZA</span>
        <StatusPill value={card.status} />
      </span>

      <span className="bank-card-chip" aria-hidden="true" />
      <span className="card-number">•••• •••• •••• {card.last_four}</span>

      <span className="card-meta-row">
        <span>
          <small>Referencia</small>
          <span className="mono">{reference}</span>
        </span>
        <span>
          <small>Vence</small>
          <span className="mono">{expiry}</span>
        </span>
      </span>
    </button>
  )
}

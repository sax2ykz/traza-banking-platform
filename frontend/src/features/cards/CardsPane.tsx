import { useState } from 'react'
import type { Account, Card } from '../../types'
import { CardDetailsModal } from './CardDetailsModal'
import { CardPreview } from './CardPreview'

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
}

function cardExpiry(createdAt: string): string {
  const created = new Date(createdAt)
  const month = String(created.getMonth() + 1).padStart(2, '0')
  const year = String((created.getFullYear() + 4) % 100).padStart(2, '0')
  return `${month}/${year}`
}

export function CardsPane({ selected, cards, busy, issue }: { selected: Account | null; cards: Card[]; busy: boolean; issue: () => void }) {
  const [selectedCard, setSelectedCard] = useState<Card | null>(null)

  return (
    <section className="customer-product-pane cards-pane">
      <div className="section-title customer-section-header">
        <div>
          <div className="eyebrow">Medios de pago</div>
          <h2>Tarjetas</h2>
        </div>
        {selected && (
          <button className="primary-button compact" disabled={busy} onClick={issue}>
            Emitir tarjeta
          </button>
        )}
      </div>

      <div className="customer-pane-body" aria-live="polite">
        {!selected ? (
          <p className="subtle customer-empty-state">Selecciona una cuenta.</p>
        ) : cards.length === 0 ? (
          <p className="subtle customer-empty-state">La cuenta seleccionada no tiene tarjetas.</p>
        ) : (
          <div className="card-grid">
            {cards.map((card) => (
              <CardPreview
                key={card.id}
                card={card}
                expiry={cardExpiry(card.created_at)}
                reference={shortId(card.card_reference)}
                onOpen={() => setSelectedCard(card)}
              />
            ))}
          </div>
        )}
      </div>

      <p className="footnote">CVV: ••• · Datos de tarjeta protegidos</p>

      {selectedCard && (
        <CardDetailsModal
          key={selectedCard.id}
          card={selectedCard}
          expiry={cardExpiry(selectedCard.created_at)}
          maskedReference={shortId(selectedCard.card_reference)}
          onClose={() => setSelectedCard(null)}
        />
      )}
    </section>
  )
}

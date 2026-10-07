import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { StatusPill } from '../../components/ui/StatusPill'
import type { Card } from '../../types'

const REVEAL_SECONDS = 15

interface CardDetailsModalProps {
  card: Card
  expiry: string
  maskedReference: string
  onClose: () => void
}

export function CardDetailsModal({ card, expiry, maskedReference, onClose }: CardDetailsModalProps) {
  const [revealed, setRevealed] = useState(false)
  const [secondsRemaining, setSecondsRemaining] = useState(REVEAL_SECONDS)
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow

    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }

      if (event.key !== 'Tab') return

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      )

      if (!focusable || focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      previouslyFocused?.focus()
    }
  }, [onClose])

  useEffect(() => {
    if (!revealed) return

    const timer = window.setTimeout(() => {
      if (secondsRemaining <= 1) {
        setRevealed(false)
        setSecondsRemaining(REVEAL_SECONDS)
        return
      }

      setSecondsRemaining((current) => current - 1)
    }, 1000)

    return () => window.clearTimeout(timer)
  }, [revealed, secondsRemaining])

  function revealAvailableData() {
    setSecondsRemaining(REVEAL_SECONDS)
    setRevealed(true)
  }

  return createPortal(
    <div
      className="app-shell card-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="card-details-modal"
        id="card-details-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="card-details-title"
        aria-describedby="card-details-description"
      >
        <div className="card-modal-header">
          <div>
            <div className="eyebrow">Detalle protegido</div>
            <h2 id="card-details-title">Tarjeta terminada en {card.last_four}</h2>
          </div>
          <button
            className="card-modal-close"
            type="button"
            ref={closeButtonRef}
            aria-label="Cerrar detalle de tarjeta"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <p className="subtle" id="card-details-description">
          Consulta la información disponible sin exponer credenciales que TRAZA no almacena en esta vista.
        </p>

        <div className="card-modal-preview" aria-hidden="true">
          <div className="bank-card-top">
            <span className="bank-card-brand">TRAZA</span>
            <StatusPill value={card.status} />
          </div>
          <div className="bank-card-chip" />
          <div className="card-number">•••• •••• •••• {card.last_four}</div>
        </div>

        <dl className="card-details-grid">
          <div>
            <dt>Número de tarjeta</dt>
            <dd className="mono">•••• •••• •••• {card.last_four}</dd>
          </div>
          <div>
            <dt>CVV</dt>
            <dd className="mono">•••</dd>
          </div>
          <div>
            <dt>Referencia</dt>
            <dd className="mono">{revealed ? card.card_reference : maskedReference}</dd>
          </div>
          <div>
            <dt>Vencimiento</dt>
            <dd className="mono">{expiry}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd><StatusPill value={card.status} /></dd>
          </div>
        </dl>

        <div className="card-privacy-note">
          El número completo y el CVV no están disponibles en el contrato actual y permanecen protegidos.
        </div>

        <div className="card-modal-actions">
          <span className="card-visibility-timer" aria-live="polite">
            {revealed ? `Tiempo visible: ${secondsRemaining}s` : `Tiempo disponible: ${REVEAL_SECONDS}s`}
          </span>
          <button className="primary-button" type="button" onClick={revealAvailableData}>
            {revealed ? 'Reiniciar tiempo' : 'Mostrar datos'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

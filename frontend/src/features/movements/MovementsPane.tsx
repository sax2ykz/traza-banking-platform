import { StatusPill } from '../../components/ui/StatusPill'
import type { Account, Movement } from '../../types'

function money(value: string | number, currency = 'PEN'): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `${currency} ${value}`
  return new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount)
}

function dateTime(value: string): string {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('es-PE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function uiLabel(value: string): string {
  const labels: Record<string, string> = {
    SAVINGS: 'Ahorros',
    CHECKING: 'Corriente',
    ACTIVE: 'Activa',
    PENDING: 'Pendiente',
    APPROVED: 'Aprobado',
    VERIFIED: 'Verificado',
    REJECTED: 'Rechazado',

    MATCH: 'Coincidencia',
    MISMATCH: 'Datos no coinciden',
    NOT_FOUND: 'No encontrado',
    NOT_CURRENT: 'No vigente',
    CURRENT: 'Vigente',
    COINCIDE: 'Coincide',
    'NO COINCIDE': 'No coincide',

    BLOCKED: 'Bloqueada',
    FROZEN: 'Congelada',
    COMPLETED: 'Completada',
    PAID: 'Pagada',
    SCHEDULED: 'Programada',
    PARTIAL: 'Parcial',
    DEPOSIT: 'Depósito',
    WITHDRAW: 'Retiro',
    WITHDRAWAL: 'Retiro',
    TRANSFER: 'Transferencia',
    INTERBANK_TRANSFER: 'Transferencia interbancaria',
    TRANSFER_IN: 'Transferencia recibida',
    TRANSFER_OUT: 'Transferencia enviada',
    LOAN_DISBURSEMENT: 'Desembolso de préstamo',
    CREDIT: 'Abono',
    DEBIT: 'Cargo',
    CUSTOMER: 'Cliente',
    ADMIN: 'Administrador',
    OK: 'OK',
  }

  return labels[value.toUpperCase()] ?? value
}

export function MovementsPane({ selected, movements, loading }: { selected: Account | null; movements: Movement[]; loading: boolean }) {
  return (
    <section className="customer-product-pane movements-pane">
      <div className="section-title customer-section-header">
        <div>
          <div className="eyebrow">Trazabilidad</div>
          <h2>Movimientos</h2>
        </div>
        {selected && <StatusPill value={selected.status} />}
      </div>

      <div className="customer-pane-body" aria-live="polite">
        {!selected ? (
          <p className="subtle customer-empty-state">Selecciona una cuenta.</p>
        ) : loading ? (
          <p className="subtle customer-empty-state">Cargando movimientos…</p>
        ) : movements.length === 0 ? (
          <p className="subtle customer-empty-state">No existen movimientos todavía.</p>
        ) : (
          <div className="data-table-wrap movements-table-wrap">
            <table className="financial-table movements-table" aria-label="Movimientos de la cuenta">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>Dirección</th>
                  <th>Monto</th>
                  <th>Saldo posterior</th>
                </tr>
              </thead>
              <tbody>
                {movements.map((movement) => (
                  <tr key={movement.id}>
                    <td className="movement-date">{dateTime(movement.created_at)}</td>
                    <td className="movement-type">{uiLabel(movement.transaction_type)}</td>
                    <td>
                      <span className={`movement-direction ${movement.direction === 'CREDIT' ? 'credit' : 'debit'}`}>
                        {uiLabel(movement.direction)}
                      </span>
                    </td>
                    <td className="financial-amount movement-amount">
                      {money(movement.amount, movement.currency)}
                    </td>
                    <td className="financial-amount balance-after">
                      {money(movement.balance_after, movement.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

import { StatusPill } from '../../components/ui/StatusPill'
import type { LoanApplication } from '../../types'

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

export function LoanApplicationsTable({ loans }: { loans: LoanApplication[] }) {
  return (
    <div className="data-table-wrap top-gap loan-applications-wrap">
      <table className="financial-table loan-applications-table" aria-label="Solicitudes de préstamo">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Monto</th>
            <th>Plazo</th>
            <th>Finalidad</th>
            <th>Estado</th>
            <th>Evaluación</th>
          </tr>
        </thead>
        <tbody>
          {loans.map((loan) => (
            <tr key={loan.id}>
              <td className="loan-request-date">{dateTime(loan.requested_at)}</td>
              <td className="financial-amount">{money(loan.requested_amount, loan.currency)}</td>
              <td className="loan-term-cell">{loan.term_months} meses</td>
              <td className="loan-purpose-cell">{loan.purpose}</td>
              <td><StatusPill value={loan.status} /></td>
              <td>{loan.status === 'PENDING' ? 'Pendiente' : 'Completada'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {loans.length === 0 && (
        <p className="subtle customer-empty-state">No existen solicitudes de préstamo.</p>
      )}
    </div>
  )
}

import type { LoanInstallmentDetail, LoanSummary } from '../../types'

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

function loanStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    PENDING: 'Pendiente',
    APPROVED: 'Aprobado',
    ACTIVE: 'Activo',
    CLOSED: 'Cerrado',
    REJECTED: 'Rechazado',
  }
  return labels[value.toUpperCase()] ?? value
}

function disbursementLabel(value: string): string {
  const labels: Record<string, string> = {
    PENDING: 'Pendiente de programación',
    SCHEDULED: 'Programado',
    PROCESSING: 'En proceso',
    COMPLETED: 'Completado',
    FAILED: 'Fallido',
  }
  return labels[value.toUpperCase()] ?? value
}

function shortDate(value: string | null): string {
  if (!value) return '—'
  const normalized = value.length === 10 ? `${value}T00:00:00` : value
  return new Intl.DateTimeFormat('es-PE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(normalized))
}

export function ApprovedLoansList({
  approvedLoans,
  loadingApproved,
  loanError,
  scheduleLoanId,
  installments,
  toggleSchedule,
}: {
  approvedLoans: LoanSummary[]
  loadingApproved: boolean
  loanError: string
  scheduleLoanId: string | null
  installments: LoanInstallmentDetail[]
  toggleSchedule: (loanId: string) => Promise<void>
}) {
  return (
    <section className="approved-loans-section" aria-live="polite">
      {loanError && <div className="message error block-gap" role="alert">{loanError}</div>}

      {loadingApproved ? (
        <p className="subtle customer-empty-state">Cargando préstamos...</p>
      ) : approvedLoans.length === 0 ? (
        <p className="subtle customer-empty-state">No tienes préstamos aprobados.</p>
      ) : (
        <div className="approved-loan-list">
          {approvedLoans.map((loan) => (
            <article className="approved-loan-card" key={loan.id}>
              <div className="approved-loan-head">
                <div>
                  <div className="eyebrow">Préstamo de consumo</div>
                  <h3>{money(loan.principal, loan.currency)}</h3>
                </div>
                <span className={`status-pill ${['APPROVED', 'ACTIVE'].includes(loan.status.toUpperCase()) ? 'success' : loan.status.toUpperCase() === 'REJECTED' ? 'danger' : 'neutral'}`}>
                  {loanStatusLabel(loan.status)}
                </span>
              </div>

              <div className="approved-loan-metrics">
                <div className="loan-metric"><span>TEA</span><strong>{Number(loan.annual_rate).toFixed(2)}%</strong></div>
                <div className="loan-metric"><span>Plazo</span><strong>{loan.term_months} meses</strong></div>
                <div className="loan-metric"><span>Cuota</span><strong>{loan.installment_amount ? money(loan.installment_amount, loan.currency) : '—'}</strong></div>
                <div className="loan-metric"><span>Próximo vencimiento</span><strong>{shortDate(loan.next_due_date)}</strong></div>
                <div className="loan-metric"><span>Total programado</span><strong>{money(loan.total_scheduled, loan.currency)}</strong></div>
                <div className="loan-metric loan-metric-emphasis"><span>Saldo pendiente</span><strong>{money(loan.outstanding_amount, loan.currency)}</strong></div>
                <div className="loan-metric"><span>Desembolso</span><strong>{disbursementLabel(loan.disbursement_status)}</strong></div>
                <div className="loan-metric"><span>Cuenta de abono</span><strong>{loan.disbursement_account_last4 ? `•••• ${loan.disbursement_account_last4}` : '—'}</strong></div>
                <div className="loan-metric"><span>Fecha de abono</span><strong>{loan.disbursed_at ? dateTime(loan.disbursed_at) : loan.scheduled_disbursement_at ? dateTime(loan.scheduled_disbursement_at) : 'Pendiente de programación'}</strong></div>
              </div>

              {loan.disbursement_status === 'SCHEDULED' && (
                <div className="review-guidance warning top-gap">
                  Tu préstamo fue aprobado. El desembolso está programado
                  {loan.scheduled_disbursement_at ? ` para ${dateTime(loan.scheduled_disbursement_at)}` : ''}
                  {loan.disbursement_account_last4 ? ` en tu cuenta terminada en ${loan.disbursement_account_last4}.` : '.'}
                </div>
              )}

              {loan.disbursement_status === 'COMPLETED' && (
                <div className="review-guidance success top-gap">
                  Desembolso completado
                  {loan.disbursed_at ? ` el ${dateTime(loan.disbursed_at)}` : ''}.
                  Revisa Movimientos para consultar el abono y tu saldo actualizado.
                </div>
              )}

              <div className="button-row">
                <button
                  type="button"
                  className="secondary-button compact"
                  onClick={() => void toggleSchedule(loan.id)}
                >
                  {scheduleLoanId === loan.id ? 'Ocultar cronograma' : 'Ver cronograma'}
                </button>
              </div>

              {scheduleLoanId === loan.id && (
                <div className="data-table-wrap loan-schedule">
                  <table className="financial-table" aria-label="Cronograma de cuotas">
                    <thead>
                      <tr>
                        <th>Cuota</th>
                        <th>Vencimiento</th>
                        <th>Monto</th>
                        <th>Pagado</th>
                        <th>Pendiente</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {installments.map((item) => (
                        <tr key={item.id}>
                          <td>{item.installment_number}</td>
                          <td>{shortDate(item.due_date)}</td>
                          <td className="financial-amount">{money(item.due_amount, loan.currency)}</td>
                          <td className="financial-amount">{money(item.paid_amount, loan.currency)}</td>
                          <td className="financial-amount">{money(item.outstanding_amount, loan.currency)}</td>
                          <td>{uiLabel(item.status)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

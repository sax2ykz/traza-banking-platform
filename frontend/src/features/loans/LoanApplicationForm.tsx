import type { FormEvent } from 'react'

import type { Account } from '../../types'

function money(value: string | number, currency = 'PEN'): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `${currency} ${value}`
  return new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount)
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

export function LoanApplicationForm({
  eligibleDisbursementAccounts,
  disbursementAccountId,
  setDisbursementAccountId,
  submit,
  amount,
  setAmount,
  currency,
  setCurrency,
  term,
  setTerm,
  purpose,
  setPurpose,
  busy,
}: {
  eligibleDisbursementAccounts: Account[]
  disbursementAccountId: string
  setDisbursementAccountId: (value: string) => void
  submit: (e: FormEvent) => void
  amount: string
  setAmount: (v: string) => void
  currency: 'PEN' | 'USD'
  setCurrency: (v: 'PEN' | 'USD') => void
  term: 6 | 12 | 18 | 24 | 36 | 48 | 60
  setTerm: (v: 6 | 12 | 18 | 24 | 36 | 48 | 60) => void
  purpose: string
  setPurpose: (v: string) => void
  busy: boolean
}) {
  return (
    <section className="customer-product-pane loan-application-pane">
      <div className="section-title customer-section-header">
        <div>
          <div className="eyebrow">Crédito de consumo</div>
          <h2>Solicitudes</h2>
        </div>
      </div>

      <form className="loan-form customer-loan-form" onSubmit={submit} aria-busy={busy}>
        <label>
          <span className="field-label">Monto</span>
          <input
            type="number"
            min="500"
            max="50000"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </label>

        <label>
          <span className="field-label">Moneda</span>
          <select value={currency} onChange={(e) => setCurrency(e.target.value as 'PEN' | 'USD')}>
            <option value="PEN">PEN</option>
            <option value="USD">USD</option>
          </select>
        </label>

        <label>
          <span className="field-label">Cuenta de abono</span>
          <select
            value={disbursementAccountId}
            onChange={(e) => setDisbursementAccountId(e.target.value)}
            required
          >
            <option value="">Selecciona una cuenta</option>
            {eligibleDisbursementAccounts.map((account) => (
              <option key={account.id} value={account.id}>
                {uiLabel(account.account_type)} · ••••{account.account_number.slice(-4)} · {money(account.balance, account.currency)}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="field-label">Plazo</span>
          <select
            value={term}
            onChange={(e) =>
              setTerm(Number(e.target.value) as 6 | 12 | 18 | 24 | 36 | 48 | 60)
            }
          >
            {[6, 12, 18, 24, 36, 48, 60].map((value) => (
              <option key={value} value={value}>
                {value} meses
              </option>
            ))}
          </select>
        </label>

        <label className="loan-purpose">
          <span className="field-label">Finalidad</span>
          <input
            minLength={5}
            maxLength={120}
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            required
          />
        </label>

        <button className="primary-button" disabled={busy}>
          Enviar a revisión
        </button>
      </form>
    </section>
  )
}

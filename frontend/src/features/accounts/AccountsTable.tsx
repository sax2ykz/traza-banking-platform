import { StatusPill } from '../../components/ui/StatusPill'
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

export function AccountsTable({ accounts }: { accounts: Account[] }) {
  return (
    <div className="data-table-wrap accounts-table-wrap">
      <table className="financial-table accounts-table" aria-label="Cuentas y saldos">
        <thead>
          <tr>
            <th>Cuenta</th>
            <th>Tipo</th>
            <th>Moneda</th>
            <th>Saldo</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => (
            <tr key={account.id}>
              <td className="mono account-number-cell">{account.account_number}</td>
              <td>{uiLabel(account.account_type)}</td>
              <td className="currency-cell">{account.currency}</td>
              <td className="financial-amount account-balance-cell">
                {money(account.balance, account.currency)}
              </td>
              <td><StatusPill value={account.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

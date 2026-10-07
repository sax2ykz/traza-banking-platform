import type { FormEvent } from 'react'

import type { Account } from '../../types'
import { AccountsTable } from './AccountsTable'

export function AccountsPane({ accounts, onSubmit, accountType, setAccountType, currency, setCurrency, busy }: {
  accounts: Account[]; onSubmit: (e: FormEvent) => void; accountType: 'SAVINGS' | 'CHECKING'; setAccountType: (v: 'SAVINGS' | 'CHECKING') => void; currency: 'PEN' | 'USD'; setCurrency: (v: 'PEN' | 'USD') => void; busy: boolean
}) {
  return (
    <section className="customer-product-pane accounts-pane">
      <div className="section-title customer-section-header">
        <div>
          <div className="eyebrow">Vista consolidada</div>
          <h2>Cuentas y saldos</h2>
        </div>
      </div>

      <AccountsTable accounts={accounts} />

      <form className="inline-form account-opening-form" onSubmit={onSubmit}>
        <h3>Abrir cuenta</h3>

        <label>
          <span className="field-label">Tipo</span>
          <select
            value={accountType}
            onChange={(e) => setAccountType(e.target.value as 'SAVINGS' | 'CHECKING')}
          >
            <option value="SAVINGS">Ahorros</option>
            <option value="CHECKING">Corriente</option>
          </select>
        </label>

        <label>
          <span className="field-label">Moneda</span>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value as 'PEN' | 'USD')}
          >
            <option value="PEN">PEN</option>
            <option value="USD">USD</option>
          </select>
        </label>

        <button className="primary-button" disabled={busy}>
          Crear cuenta
        </button>
      </form>
    </section>
  )
}

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

export function AccountSidebar({
  accounts,
  selectedId,
  onSelect,
}: {
  accounts: Account[]
  selectedId: string
  onSelect: (accountId: string) => void
}) {
  return (
    <aside className="content-card account-sidebar">
      <div className="section-title">
        <div>
          <div className="eyebrow">Productos</div>
          <h2>Mis cuentas</h2>
        </div>

        <span className="queue-count">
          {accounts.length}
        </span>
      </div>

      <div className="account-list">
        {accounts.map((account) => (
          <button
            key={account.id}
            className={
              selectedId === account.id
                ? 'account-item selected'
                : 'account-item'
            }
            aria-pressed={selectedId === account.id}
            onClick={() => onSelect(account.id)}
          >
            <span className="account-item-title">
              {account.account_type === 'SAVINGS'
                ? 'Ahorros'
                : 'Corriente'}{' '}
              · {account.currency}
            </span>

            <strong className="account-item-balance">
              {money(account.balance, account.currency)}
            </strong>

            <small className="account-item-number">
              •••• {account.account_number.slice(-6)}
            </small>
          </button>
        ))}

        {accounts.length === 0 && (
          <p className="subtle customer-empty-state">
            Aún no tienes cuentas.
          </p>
        )}
      </div>
    </aside>
  )
}

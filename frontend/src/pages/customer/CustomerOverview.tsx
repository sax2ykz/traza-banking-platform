import { Metric } from '../../components/ui/Metric'
import { StatusPill } from '../../components/ui/StatusPill'
import type { Customer } from '../../types'

function money(value: string | number, currency = 'PEN'): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `${currency} ${value}`
  return new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount)
}

export function CustomerOverview({
  dbStatus,
  customer,
  accountCount,
  totalPen,
  totalUsd,
}: {
  dbStatus: string
  customer: Customer
  accountCount: number
  totalPen: number
  totalUsd: number
}) {
  return (
    <>
      <section className="hero-card">
        <div><div className="eyebrow">Banca digital</div><h1>Hola, {customer.full_name}</h1><p className="subtle">Gestiona tus productos y operaciones desde un solo lugar.</p></div>
        <div className="hero-status"><span>Base de datos</span><StatusPill value={dbStatus} /></div>
      </section>

      <section className="metrics-grid four">
        <Metric label="Verificación" value={customer.onboarding_status} note="Control humano" pill />
        <Metric label="Cuentas" value={String(accountCount)} note="Productos activos" />
        <Metric label="Saldo PEN" value={money(totalPen, 'PEN')} note="Sin conversión cambiaria" />
        <Metric label="Saldo USD" value={money(totalUsd, 'USD')} note="Sin conversión cambiaria" />
      </section>
    </>
  )
}

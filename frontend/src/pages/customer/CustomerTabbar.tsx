export type CustomerTab =
  | 'accounts'
  | 'movements'
  | 'cards'
  | 'loans'
  | 'operations'

export function CustomerTabbar({
  tab,
  onTabChange,
}: {
  tab: CustomerTab
  onTabChange: (tab: CustomerTab) => void
}) {
  return (
    <nav className="tabbar" aria-label="Módulos bancarios">
      {(
        [
          'accounts',
          'movements',
          'cards',
          'loans',
          'operations',
        ] as CustomerTab[]
      ).map((item) => (
        <button
          key={item}
          className={tab === item ? 'tab active' : 'tab'}
          aria-pressed={tab === item}
          onClick={() => onTabChange(item)}
        >
          {{
            accounts: 'Cuentas',
            movements: 'Movimientos',
            cards: 'Tarjetas',
            loans: 'Préstamos',
            operations: 'Operaciones',
          }[item]}
        </button>
      ))}
    </nav>
  )
}

import type { ReactNode } from 'react'

import { AccountSidebar } from '../../features/accounts/AccountSidebar'
import type { Account } from '../../types'

export function CustomerWorkspace({
  accounts,
  selectedId,
  onSelectAccount,
  children,
}: {
  accounts: Account[]
  selectedId: string
  onSelectAccount: (accountId: string) => void
  children: ReactNode
}) {
  return (
    <section className="workspace-grid">
      <AccountSidebar
        accounts={accounts}
        selectedId={selectedId}
        onSelect={onSelectAccount}
      />

      <section className="content-card main-workspace">
        {children}
      </section>
    </section>
  )
}

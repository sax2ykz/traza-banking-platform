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

export function StatusPill({ value }: { value: string }) {
  const normalized = value.toUpperCase().trim()

  const tone = [
    'VERIFIED',
    'OK',
    'ACTIVE',
    'COMPLETED',
    'PAID',
    'MATCH',
    'CURRENT',
    'COINCIDE',
    'VIGENTE',
  ].includes(normalized)
    ? 'success'
    : ['PENDING', 'SCHEDULED', 'PARTIAL', 'PENDIENTE'].includes(normalized)
      ? 'warning'
      : [
          'REJECTED',
          'BLOCKED',
          'FROZEN',
          'MISMATCH',
          'NOT_FOUND',
          'NOT_CURRENT',
          'NO COINCIDE',
        ].includes(normalized)
        ? 'danger'
        : 'neutral'

  return <span className={`status-pill ${tone}`}>{uiLabel(value)}</span>
}

function ctLabel(value: string | null): string {
  if (!value) return '—'

  const labels: Record<string, string> = {
    UP: 'Operativo',
    SUCCEEDED: 'Correcto',
    COMPLETED: 'Completada',
    QUALITY_GATE_FAILED: 'Control no aprobado',
    FAILED: 'Fallido',
    PUBLISHED: 'Publicado',
    APPROVED: 'Aprobado',
    VERIFIED: 'Verificado',
    REJECTED: 'Rechazado',
    SUCCESS: 'Correcto',
    ACKNOWLEDGED: 'Revisado',
    PENDING: 'Pendiente',
    SCHEDULED: 'Programado',
    ACTIVE: 'Activo',
    DATA_QUALITY: 'Calidad de datos',

    TRANSFER: 'Transferencia',
    INTERBANK_TRANSFER: 'Transferencia interbancaria',
    DEPOSIT: 'Depósito',
    WITHDRAWAL: 'Retiro',
    TRANSFER_IN: 'Transferencia recibida',
    TRANSFER_OUT: 'Transferencia enviada',
    LOAN_DISBURSEMENT: 'Desembolso de préstamo',

    DEBIT: 'Cargo',
    CREDIT: 'Abono',

    ADMIN: 'Administrador',
    STAFF: 'Personal autorizado',
    SYSTEM: 'Sistema BancoCloud',
    SERVICE: 'Servicio BancoCloud',

    MATCH: 'Coincidencia',

    LOAN_APPLICATION_REVIEW:
      'Revisión crediticia',

    LOAN_DISBURSEMENT_SCHEDULED:
      'Desembolso programado',

    LOAN_DISBURSEMENT_COMPLETED:
      'Desembolso completado',

    LOAN_DISBURSEMENT_FAILED:
      'Error de desembolso',

    SYNTHETIC_ONBOARDING_REVIEW:
      'Revisión de identidad',

    FINANCIAL_OPERATION:
      'Operación financiera registrada',

    SYNTHETIC_FINANCIAL_OPERATION:
      'Operación financiera registrada',
  }

  return labels[value.toUpperCase()] ?? value
}


function ctTone(value: string | null): string {
  const normalized =
    (value ?? '').toUpperCase()

  if (
    [
      'UP',
      'SUCCEEDED',
      'COMPLETED',
      'PUBLISHED',
      'APPROVED',
      'VERIFIED',
      'SUCCESS',
      'ACKNOWLEDGED',
      'MATCH',
    ].includes(normalized)
  ) {
    return 'success'
  }

  if (
    [
      'QUALITY_GATE_FAILED',
      'FAILED',
      'REJECTED',
    ].includes(normalized)
  ) {
    return 'danger'
  }

  return 'neutral'
}

export function CtStatus({
  value,
}: {
  value: string | null
}) {
  return (
    <span
      className={`ct-status ${ctTone(value)}`}
    >
      {ctLabel(value)}
    </span>
  )
}

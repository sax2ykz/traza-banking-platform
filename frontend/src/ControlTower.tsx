import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import {
  analyzeControlTowerDataOps,
  getControlTowerCopilotHistory,
  getControlTowerDataOps,
  getControlTowerDecisions,
  getControlTowerOperations,
  getControlTowerOperationTrace,
  getControlTowerOverview,
  reviewControlTowerCopilot,
  runControlTowerDataOps,
  runControlTowerQualityTest,
} from './api'

import type {
  CopilotHistoryItem,
  ControlTowerDataOps,
  ControlTowerAuditEvent,
  ControlTowerDataOpsRun,
  ControlTowerDecision,
  ControlTowerOperation,
  ControlTowerOperationTrace,
  ControlTowerOverview,
} from './types'
import { AccordionHeader } from './features/control-tower/components/AccordionHeader'
import { CtStatus } from './features/control-tower/components/CtStatus'
import { FlowStrip } from './features/control-tower/components/FlowStrip'

import './control-tower.css'


function ctMoney(
  value: string | number,
  currency = 'PEN',
): string {
  const amount = Number(value)

  if (!Number.isFinite(amount)) {
    return `${currency} ${value}`
  }

  return new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount)
}


function ctDate(value: string | null): string {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('es-PE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}


function ctShort(value: string | null): string {
  if (!value) return '—'

  return value.length > 16
    ? `${value.slice(0, 8)}…${value.slice(-4)}`
    : value
}


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


function ctAuditTransferSummary(
  event: ControlTowerAuditEvent,
): string | null {
  const details = event.details ?? {}
  const scope = details.transfer_scope

  if (scope === 'OWN_ACCOUNTS') {
    return 'Destino: otra cuenta del mismo cliente.'
  }

  if (scope === 'BANCOCLOUD_THIRD_PARTY') {
    const last4 =
      typeof details.target_account_last4 === 'string'
        ? details.target_account_last4
        : null

    return last4
      ? `Destino: tercero BancoCloud · cuenta ••••${last4}.`
      : 'Destino: tercero BancoCloud.'
  }

  if (scope === 'INTERBANK') {
    const bank =
      typeof details.destination_bank_name === 'string'
        ? details.destination_bank_name
        : 'otro banco'

    const masked =
      typeof details.external_account_masked === 'string'
        ? details.external_account_masked
        : null

    return masked
      ? `Destino: ${bank} · CCI ${masked}.`
      : `Destino: ${bank}.`
  }

  return null
}


function ctLedgerAccount(
  accountId: string | null,
  clearingAccountCode: string | null,
): string {
  if (accountId) {
    return `Cuenta vinculada · ${ctShort(accountId)}`
  }

  if (
    clearingAccountCode ===
    'CASH_CLEARING' ||
    clearingAccountCode ===
    'SYNTHETIC_CASH'
  ) {
    return 'Cuenta interna de caja'
  }

  if (clearingAccountCode) {
    return 'Cuenta interna de compensación'
  }

  return 'Cuenta contable interna'
}

function ctSourceName(
  source: string,
): string {
  const labels: Record<string, string> = {
    banking_operations:
      'Operaciones bancarias',
    transactions:
      'Movimientos',
    accounts:
      'Cuentas',
    customers:
      'Clientes',
    loan_applications:
      'Solicitudes de préstamo',
    loans:
      'Préstamos',
    loan_installments:
      'Cuotas de préstamo',
    loan_payments:
      'Pagos de préstamo',
  }

  return labels[source] ?? source
}


function ctRuleName(
  rule: string,
): string {
  const labels: Record<string, string> = {
    record_validation:
      'Validación del registro',
  }

  return labels[rule] ?? rule
}


function ctReason(
  reason: string,
): string {
  const normalized =
    reason.trim()

  if (
    normalized.toLowerCase().includes(
      'currency: moneda no permitida',
    )
  ) {
    return 'Moneda no permitida'
  }

  return normalized
}


function ctDisplayKey(
  value: string,
): string {
  return value
    .toLowerCase()
    .replace(/[.,;:]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}


function ctUniqueDisplayItems(
  values: string[],
  mapper: (value: string) => string,
): string[] {
  const seen = new Set<string>()
  const result: string[] = []

  values.forEach((value) => {
    const mapped = mapper(value).trim()

    if (!mapped) {
      return
    }

    const key = ctDisplayKey(mapped)

    if (seen.has(key)) {
      return
    }

    seen.add(key)
    result.push(mapped)
  })

  return result
}


function ctCopilotRiskText(
  value: string,
): string {
  const normalized =
    value.toLowerCase()

  const qualityRatio = value.match(
    /(?:quality_gates_passed|quality_passed)=(\d+)\s*\/\s*(\d+)/i,
  )

  if (qualityRatio) {
    const failed =
      Number(qualityRatio[2]) -
      Number(qualityRatio[1])

    const failedText =
      failed === 1
        ? 'un control requiere revisión'
        : `${failed} controles requieren revisión`

    return (
      'La ejecución no superó todos los controles ' +
      `de calidad: aprobó ${qualityRatio[1]} de ` +
      `${qualityRatio[2]} y ${failedText}.`
    )
  }

  const qualityTotal = value.match(
    /quality_total=(\d+)/i,
  )
  const qualityPassed = value.match(
    /quality_passed=(\d+)/i,
  )
  const qualityFailed = value.match(
    /quality_failed=(\d+)/i,
  )

  if (
    qualityTotal &&
    qualityPassed &&
    qualityFailed &&
    Number(qualityFailed[1]) > 0
  ) {
    const failed = Number(qualityFailed[1])
    const failedText =
      failed === 1
        ? 'un control requiere revisión'
        : `${failed} controles requieren revisión`

    return (
      'La ejecución no superó todos los controles ' +
      `de calidad: aprobó ${qualityPassed[1]} de ` +
      `${qualityTotal[1]} y ${failedText}.`
    )
  }

  if (
    normalized.includes(
      'quality_gate_failed',
    )
  ) {
    return (
      'La ejecución no superó todos los ' +
      'controles de calidad.'
    )
  }

  if (
    normalized.includes(
      'moneda no permitid',
    ) ||
    normalized.includes(
      'failure_reason=moneda',
    )
  ) {
    return (
      'Un registro fue aislado porque contiene ' +
      'una moneda no permitida.'
    )
  }

  if (
    normalized.includes(
      'para evitar que un dato inválido llegara a la versión gold',
    ) ||
    normalized.includes(
      'para evitar que un dato invalido llegara a la version gold',
    ) ||
    normalized.includes(
      'no llegara a la versión gold',
    ) ||
    normalized.includes(
      'no llegara a la version gold',
    )
  ) {
    return (
      'El registro inválido quedó aislado y no fue ' +
      'incorporado a la versión Gold.'
    )
  }

  const quarantined = value.match(
    /(?:rows_quarantined|records_quarantined|quarantine_records)=(\d+)/i,
  )

  if (quarantined) {
    const amount = Number(quarantined[1])

    return amount === 1
      ? (
          'Un registro fue aislado durante el ' +
          'control de calidad.'
        )
      : (
          `${amount} registros fueron aislados ` +
          'durante el control de calidad.'
        )
  }

  if (
    normalized.includes(
      'no reemplazó la versión gold vigente',
    ) ||
    normalized.includes(
      'no reemplazo la version gold vigente',
    ) ||
    normalized.includes(
      'gold_protected=true',
    ) ||
    normalized.includes(
      'is_current_gold=false',
    ) ||
    (
      normalized.includes(
        'current_gold',
      ) &&
      normalized.includes(
        'published',
      )
    )
  ) {
    return (
      'La versión Gold vigente se mantuvo ' +
      'protegida y no fue reemplazada por esta ' +
      'ejecución.'
    )
  }

  if (
    normalized.includes(
      'gold_published=false',
    )
  ) {
    return (
      'La ejecución no publicó una nueva ' +
      'versión Gold.'
    )
  }

  if (
    normalized.includes(
      'transaction_total_not_equal_ledger_total',
    ) ||
    normalized.includes(
      'reconciliation_status_mismatch',
    ) ||
    normalized.includes(
      'reconciliation_status=mismatch',
    )
  ) {
    return (
      'Los movimientos y los asientos contables ' +
      'no coinciden y requieren revisión.'
    )
  }

  const difference = value.match(
    /difference(?:_of|=)_?(\d+(?:\.\d+)?)/i,
  )

  if (difference) {
    return (
      `La conciliación presenta una diferencia ` +
      `de ${difference[1]} que requiere revisión.`
    )
  }

  if (
    normalized.includes(
      'identity_result=mismatch',
    )
  ) {
    return (
      'La información de identidad presenta una ' +
      'inconsistencia que requiere revisión.'
    )
  }

  if (
    normalized.includes(
      'onboarding_status=pending',
    )
  ) {
    return (
      'La verificación de identidad permanece ' +
      'pendiente de revisión.'
    )
  }

  if (
    normalized.includes(
      'human_decision=not_yet_performed',
    )
  ) {
    return (
      'Todavía no se ha registrado una decisión ' +
      'humana para este caso.'
    )
  }

  if (
    normalized.includes(
      'operation_status=unknown',
    )
  ) {
    return (
      'El estado final de la operación no está ' +
      'confirmado.'
    )
  }

  if (
    /^(?:quarantine_source_table|quarantine_rule_name|failed_rule|failed_field)=/i.test(
      value.trim(),
    )
  ) {
    return ''
  }

  if (
    /\b[a-z][a-z0-9_]{2,}\s*=\s*/i.test(value) ||
    /\b[a-z]+_[a-z0-9_]+\b/i.test(value)
  ) {
    return ''
  }

  return value
    .replace(
      /\bQuarantine\b/gi,
      'registros aislados',
    )
    .replace(
      /\bcurrency\b/gi,
      'moneda',
    )
    .replace(
      /\s+/g,
      ' ',
    )
    .trim()
}


function ctCopilotRiskItems(
  values: string[],
  run: ControlTowerDataOpsRun | null = null,
): string[] {
  const items = ctUniqueDisplayItems(
    values,
    ctCopilotRiskText,
  )

  const hasPreciseQuality = items.some(
    (item) =>
      item.startsWith(
        'La ejecución no superó todos los controles de calidad:',
      ),
  )

  const hasSpecificQuarantine = items.some(
    (item) =>
      item.includes(
        'moneda no permitid',
      ),
  )

  const filtered = items.filter((item) => {
    if (
      hasPreciseQuality &&
      item ===
        'La ejecución no superó todos los controles de calidad.'
    ) {
      return false
    }

    if (
      hasSpecificQuarantine &&
      item ===
        'Un registro fue aislado durante el control de calidad.'
    ) {
      return false
    }

    return true
  })

  function priority(item: string): number {
    if (
      item.startsWith(
        'La ejecución no superó todos los controles de calidad:',
      )
    ) {
      return 10
    }

    if (item.includes('moneda no permitid')) {
      return 20
    }

    if (
      item.includes('no fue incorporado a la versión Gold')
    ) {
      return 30
    }

    if (
      item.includes('versión Gold vigente se mantuvo protegida')
    ) {
      return 40
    }

    return 50
  }

  const enriched = [...filtered]

  const containmentText =
    run &&
    run.rows_quarantined > 0 &&
    (
      run.status === 'QUALITY_GATE_FAILED' ||
      run.quality_failed > 0
    )
      ? (
          run.rows_quarantined === 1
            ? (
                'El registro inválido quedó aislado y no fue ' +
                'incorporado a la versión Gold.'
              )
            : (
                `Los ${run.rows_quarantined} registros inválidos ` +
                'quedaron aislados y no fueron incorporados a la ' +
                'versión Gold.'
              )
        )
      : null

  if (
    containmentText &&
    !enriched.some(
      (item) =>
        ctDisplayKey(item) ===
        ctDisplayKey(containmentText),
    )
  ) {
    enriched.push(containmentText)
  }

  return enriched.sort(
    (a, b) => priority(a) - priority(b),
  )
}


function ctCopilotPendingText(
  value: string,
): string {
  const normalized =
    value.toLowerCase()

  if (
    normalized.includes(
      'identificador',
    ) &&
    (
      normalized.includes(
        'cuarentena',
      ) ||
      normalized.includes(
        'quarantine',
      )
    )
  ) {
    return (
      'Identificar el registro aislado que ' +
      'originó la observación.'
    )
  }

  if (
    normalized.includes(
      'valor exacto',
    ) &&
    (
      normalized.includes('currency') ||
      normalized.includes('moneda')
    )
  ) {
    return (
      'Confirmar el valor de moneda que fue ' +
      'rechazado.'
    )
  }

  if (
    normalized.includes('record_validation') ||
    (
      normalized.includes('definición') &&
      normalized.includes('versión') &&
      normalized.includes('regla')
    ) ||
    (
      normalized.includes('definicion') &&
      normalized.includes('version') &&
      normalized.includes('regla')
    )
  ) {
    return (
      'Confirmar la definición y versión de la ' +
      'regla de validación del registro aplicada ' +
      'en esta ejecución.'
    )
  }

  if (
    normalized.includes('regla') &&
    (
      normalized.includes('fall') ||
      normalized.includes('quality') ||
      normalized.includes('validaci')
    )
  ) {
    return (
      'Confirmar la regla de calidad aplicada ' +
      'y el motivo exacto de la observación.'
    )
  }

  if (
    normalized.includes(
      'normalizaci',
    ) ||
    normalized.includes(
      'lista blanca',
    ) ||
    normalized.includes(
      'monedas permitidas',
    )
  ) {
    return (
      'Confirmar el catálogo de monedas ' +
      'permitidas y las reglas de validación.'
    )
  }

  if (
    normalized.includes('logs') ||
    normalized.includes(
      'trazas',
    ) ||
    normalized.includes(
      'auditoría',
    )
  ) {
    return (
      'Revisar el registro técnico de la ' +
      'ejecución para identificar errores y ' +
      'tiempos del proceso.'
    )
  }

  if (
    (
      normalized.includes(
        'fecha',
      ) &&
      normalized.includes(
        'hora',
      )
    ) ||
    normalized.includes(
      'timestamp',
    ) ||
    normalized.includes(
      'usuario/servicio',
    )
  ) {
    return (
      'Confirmar la fecha, hora y origen que ' +
      'inició la ejecución.'
    )
  }

  if (
    normalized.includes(
      'impacto',
    ) ||
    normalized.includes(
      'downstream',
    ) ||
    (
      normalized.includes(
        'proceso',
      ) &&
      normalized.includes(
        'reporte',
      )
    )
  ) {
    return (
      'Verificar si algún proceso, reporte o ' +
      'tablero podría verse afectado.'
    )
  }

  if (
    normalized.includes(
      're-procesamiento',
    ) ||
    normalized.includes(
      'reprocesamiento',
    ) ||
    normalized.includes(
      'nuevo procesamiento',
    )
  ) {
    return (
      'Confirmar si existe un nuevo procesamiento ' +
      'programado o ejecuciones anteriores para ' +
      'comparar.'
    )
  }

  if (
    normalized.includes(
      'accion esperada',
    ) ||
    normalized.includes(
      'acción esperada',
    ) ||
    normalized.includes(
      'equipo de negocio',
    ) ||
    (
      normalized.includes(
        'correcci',
      ) &&
      normalized.includes(
        'manual',
      )
    )
  ) {
    return (
      'Definir con el equipo responsable si el ' +
      'dato debe corregirse automáticamente o ' +
      'mediante revisión manual.'
    )
  }

  if (
    normalized.includes(
      'identificador único de la operación',
    ) ||
    normalized.includes(
      'operation id',
    )
  ) {
    return 'Confirmar el identificador de la operación.'
  }

  if (
    normalized.includes(
      'monto y moneda',
    )
  ) {
    return 'Confirmar el monto y la moneda de la operación.'
  }

  if (
    normalized.includes(
      'cuenta origen',
    ) ||
    normalized.includes(
      'cuenta destino',
    )
  ) {
    return 'Confirmar las cuentas involucradas en la operación.'
  }

  if (
    normalized.includes(
      'tipo de operación',
    )
  ) {
    return 'Confirmar el tipo de operación registrada.'
  }

  if (
    normalized.includes(
      'transacciones implicadas',
    ) ||
    normalized.includes(
      'movimientos individuales',
    ) ||
    normalized.includes(
      'asientos contables',
    )
  ) {
    return (
      'Revisar los movimientos y asientos ' +
      'contables involucrados en la diferencia.'
    )
  }

  if (
    normalized.includes(
      'reglas o criterios de reconciliación',
    )
  ) {
    return (
      'Confirmar las reglas de conciliación ' +
      'aplicadas al caso.'
    )
  }

  if (
    normalized.includes(
      'causa del mismatch',
    ) ||
    normalized.includes(
      'causa del cotejo',
    )
  ) {
    return (
      'Revisar la evidencia que explica la ' +
      'inconsistencia de identidad.'
    )
  }

  if (
    normalized.includes(
      'documentos de identidad',
    ) ||
    normalized.includes(
      'evidencia biométrica',
    )
  ) {
    return (
      'Confirmar la evidencia utilizada en la ' +
      'verificación de identidad.'
    )
  }

  if (
    normalized.includes(
      'revisor humano',
    ) ||
    normalized.includes(
      'decisión o evaluación',
    )
  ) {
    return (
      'Confirmar si ya existe una revisión ' +
      'humana registrada para el caso.'
    )
  }

  const cleaned = value
    .replace(
      /\([^)]*(?:=|run_id|quality_|current_gold|quarantine_)[^)]*\)/gi,
      '',
    )
    .replace(
      /\bQuarantine\b/gi,
      'registros aislados',
    )
    .replace(
      /\bcurrency\b/gi,
      'moneda',
    )
    .replace(
      /\brecord_validation\b/gi,
      'regla de validación del registro',
    )
    .replace(
      /\bruns?\b/gi,
      'ejecuciones',
    )
    .replace(
      /\bdownstream\b/gi,
      'posteriores',
    )
    .replace(
      /\s+/g,
      ' ',
    )
    .trim()

  if (
    /\b[a-z][a-z0-9_]{2,}\s*=\s*/i.test(cleaned)
  ) {
    return ''
  }

  return cleaned
}


function ctCopilotPendingItems(
  values: string[],
): string[] {
  const items = ctUniqueDisplayItems(
    values,
    ctCopilotPendingText,
  )

  const source = values
    .join(' ')
    .toLowerCase()

  const looksLikeDataQuality =
    source.includes('calidad') ||
    source.includes('quality') ||
    source.includes('quarantine') ||
    source.includes('cuarentena') ||
    source.includes('registro aislado') ||
    source.includes('moneda') ||
    source.includes('record_validation')

  if (looksLikeDataQuality) {
    const dateOrigin =
      'Confirmar la fecha, hora y origen que inició la ejecución.'

    const remediation =
      'Definir con el equipo responsable si el dato debe ' +
      'corregirse automáticamente o mediante revisión manual.'

    if (
      !items.some(
        (item) =>
          item.includes('fecha, hora y origen'),
      )
    ) {
      items.push(dateOrigin)
    }

    if (
      !items.some(
        (item) =>
          item.includes('equipo responsable'),
      )
    ) {
      items.push(remediation)
    }
  }

  return ctUniqueDisplayItems(
    items,
    (value) => value,
  )
}


function ctCopilotNextStep(
  value: string,
): string {
  const normalized = value.toLowerCase()

  if (
    normalized.includes('quarantine') ||
    normalized.includes('cuarentena') ||
    normalized.includes('quality')
  ) {
    return (
      'Revisar el registro aislado y la regla ' +
      'de calidad que no fue aprobada. Confirmar ' +
      'la causa antes de volver a ejecutar el ' +
      'proceso. Hasta completar la revisión, ' +
      'la versión Gold vigente permanece ' +
      'protegida.'
    )
  }

  return value
}


function ctCopilotReviewNote(
  value: string | null,
): string {
  if (!value) {
    return (
      'El an\u00e1lisis fue revisado por un ' +
      'administrador.'
    )
  }

  const normalized = value.toLowerCase()

  if (
    normalized.includes('gold') &&
    (
      normalized.includes('cuarentena') ||
      normalized.includes('aislado')
    )
  ) {
    return (
      'El administrador revis\u00f3 el an\u00e1lisis. ' +
      'La versi\u00f3n Gold vigente se mantiene ' +
      'protegida mientras se revisan el registro ' +
      'aislado y la regla de calidad.'
    )
  }

  if (
    normalized.includes(
      'operations control tower',
    )
  ) {
    return (
      'El administrador revis\u00f3 el an\u00e1lisis ' +
      'desde el Centro de Operaciones. Cualquier ' +
      'acci\u00f3n posterior requiere validaci\u00f3n ' +
      'humana.'
    )
  }

  return value
}


export function ControlTower() {
  const [overview, setOverview] =
    useState<ControlTowerOverview | null>(
      null,
    )

  const [operations, setOperations] =
    useState<ControlTowerOperation[]>([])

  const [decisions, setDecisions] =
    useState<ControlTowerDecision[]>([])

  const [dataOps, setDataOps] =
    useState<ControlTowerDataOps | null>(
      null,
    )

  const [trace, setTrace] =
    useState<ControlTowerOperationTrace | null>(
      null,
    )

  const [
    selectedOperationId,
    setSelectedOperationId,
  ] = useState<string | null>(null)

  const [loading, setLoading] =
    useState(true)

  const [traceLoading, setTraceLoading] =
    useState(false)

  const [error, setError] =
    useState('')

  const [towerOpen, setTowerOpen] =
    useState(true)

  const [
    operationsOpen,
    setOperationsOpen,
  ] = useState(true)

  const [
    decisionsOpen,
    setDecisionsOpen,
  ] = useState(false)

  const [
    dataOpsOpen,
    setDataOpsOpen,
  ] = useState(false)

  const [
    showAllDecisions,
    setShowAllDecisions,
  ] = useState(false)

  const [
  showAllDataOpsRuns,
  setShowAllDataOpsRuns,
  ] = useState(false)

  const [
    showAllQuarantine,
    setShowAllQuarantine,
  ] = useState(false)

  const [
  pendingAction,
  setPendingAction,
] = useState<'DATAOPS' | 'QUALITY' | null>(
  null,
)

const [
  actionRunning,
  setActionRunning,
] = useState<'DATAOPS' | 'QUALITY' | null>(
  null,
)

const [
  actionNotice,
  setActionNotice,
] = useState<{
  tone: 'success' | 'warning'
  text: string
} | null>(null)

  const [
    copilotHistory,
    setCopilotHistory,
  ] = useState<CopilotHistoryItem[]>([])

  const [
    selectedCopilot,
    setSelectedCopilot,
  ] = useState<CopilotHistoryItem | null>(
    null,
  )

  const [
    copilotLoadingRunId,
    setCopilotLoadingRunId,
  ] = useState<string | null>(null)

  const [
    copilotReviewing,
    setCopilotReviewing,
  ] = useState(false)


  const refreshAll =
    useCallback(async () => {
      setLoading(true)
      setError('')

      try {
        const [
          overviewResult,
          operationsResult,
          decisionsResult,
          dataOpsResult,
          copilotResult,
        ] = await Promise.all([
          getControlTowerOverview(),
          getControlTowerOperations(8),
          getControlTowerDecisions(8),
          getControlTowerDataOps(10),
          getControlTowerCopilotHistory(20),
        ])

        setOverview(overviewResult)
        setOperations(operationsResult)
        setDecisions(decisionsResult)
        setDataOps(dataOpsResult)
        setCopilotHistory(
          copilotResult.value,
        )

        setSelectedCopilot(
          (current) => {
            if (!current) {
              return current
            }

            return (
              copilotResult.value.find(
                (item) =>
                  item.correlation_id ===
                  current.correlation_id,
              ) ?? current
            )
          },
        )
      } catch (err) {
        console.error(err)

        setError(
          err instanceof Error
            ? err.message
            : 'No fue posible cargar el Centro de Operaciones.',
        )
      } finally {
        setLoading(false)
      }
    }, [])


  useEffect(() => {
    const timer =
      window.setTimeout(() => {
        void refreshAll()
      }, 0)

    return () => {
      window.clearTimeout(timer)
    }
  }, [refreshAll])


  async function toggleTrace(
    operationId: string,
  ) {
    if (
      selectedOperationId === operationId
    ) {
      setSelectedOperationId(null)
      setTrace(null)
      return
    }

    setSelectedOperationId(operationId)
    setTrace(null)
    setTraceLoading(true)
    setError('')

    try {
      const result =
        await getControlTowerOperationTrace(
          operationId,
        )

      setTrace(result)
    } catch (err) {
      console.error(err)

      setError(
        err instanceof Error
          ? err.message
          : 'No fue posible consultar la trazabilidad de la operación.',
      )
    } finally {
      setTraceLoading(false)
    }
  }


  function closeTrace() {
    setSelectedOperationId(null)
    setTrace(null)
  }

  async function executeAdminAction(
  action: 'DATAOPS' | 'QUALITY',
) {
  setPendingAction(null)
  setActionRunning(action)
  setActionNotice(null)
  setError('')

  try {
    const result =
      action === 'DATAOPS'
        ? await runControlTowerDataOps()
        : await runControlTowerQualityTest()

    if (action === 'DATAOPS') {
      setActionNotice({
        tone: 'success',
        text:
          `Proceso completado. Se publicó una nueva versión Gold ` +
          `con la ejecución ${ctShort(result.run_id)}.`,
      })
    } else {
      setActionNotice({
        tone: 'warning',
        text: result.gold_protected
          ? (
              `Prueba completada. El registro inválido fue aislado ` +
              `y la versión Gold vigente permaneció protegida. ` +
              `Ejecución ${ctShort(result.run_id)}.`
            )
          : result.message,
      })
    }

    await refreshAll()

    if (selectedOperationId) {
      try {
        const updatedTrace =
          await getControlTowerOperationTrace(
            selectedOperationId,
          )

        setTrace(updatedTrace)
      } catch {
        setTrace(null)
      }
    }
  } catch (err) {
    console.error(err)

    setError(
      err instanceof Error
        ? err.message
        : 'No fue posible ejecutar la acción administrativa.',
    )
  } finally {
    setActionRunning(null)
  }
}


  async function toggleCopilot(
    runId: string,
  ) {
    const existing =
      copilotHistory.find(
        (item) =>
          item.source_entity_id === runId,
      )

    if (existing) {
      if (
        selectedCopilot?.correlation_id ===
        existing.correlation_id
      ) {
        setSelectedCopilot(null)
      } else {
        setSelectedCopilot(existing)
      }

      return
    }

    setCopilotLoadingRunId(runId)
    setError('')

    try {
      const result =
        await analyzeControlTowerDataOps(
          runId,
        )

      const historyResult =
        await getControlTowerCopilotHistory(
          20,
        )

      setCopilotHistory(
        historyResult.value,
      )

      const persisted =
        historyResult.value.find(
          (item) =>
            item.correlation_id ===
            result.correlation_id,
        )

      setSelectedCopilot(
        persisted ?? {
          correlation_id:
            result.correlation_id,
          source_entity_type:
            'DATAOPS_RUN',
          source_entity_id: runId,
          created_at:
            new Date().toISOString(),
          prompt_version:
            result.prompt_version,
          model: result.model,
          category:
            result.analysis.category,
          confidence:
            result.analysis.confidence,
          human_review_required:
            result.analysis
              .human_review_required,
          analysis:
            result.analysis,
          human_review_status:
            result.human_review_status,
          human_review: null,
        },
      )
    } catch (err) {
      console.error(err)

      setError(
        err instanceof Error
          ? err.message
          : (
              'No fue posible completar ' +
              'el análisis del Copilot.'
            ),
      )
    } finally {
      setCopilotLoadingRunId(null)
    }
  }


  async function acknowledgeCopilot() {
    if (!selectedCopilot) {
      return
    }

    setCopilotReviewing(true)
    setError('')

    try {
      await reviewControlTowerCopilot(
        selectedCopilot.correlation_id,
        {
          decision: 'ACKNOWLEDGED',
          notes:
            'Análisis revisado desde ' +
            'Operations Control Tower. ' +
            'La revisión humana se mantiene ' +
            'antes de cualquier acci?n operativa.',
        },
      )

      const historyResult =
        await getControlTowerCopilotHistory(
          20,
        )

      setCopilotHistory(
        historyResult.value,
      )

      const updated =
        historyResult.value.find(
          (item) =>
            item.correlation_id ===
            selectedCopilot.correlation_id,
        )

      if (updated) {
        setSelectedCopilot(updated)
      }
    } catch (err) {
      console.error(err)

      setError(
        err instanceof Error
          ? err.message
          : (
              'No fue posible registrar ' +
              'la revisión humana.'
            ),
      )
    } finally {
      setCopilotReviewing(false)
    }
  }


  const latestRun =
    overview?.latest_dataops_run ?? null

  const currentGold =
    overview?.current_gold ?? null

  const protectedGold =
    Boolean(
      latestRun &&
      currentGold &&
      latestRun.status !== 'SUCCEEDED' &&
      currentGold.publication_status ===
        'PUBLISHED' &&
      latestRun.run_id !==
        currentGold.source_run_id,
    )


  const currentHumanDecisions =
    decisions.filter(
      (decision) =>
        decision.human_decision === 'true',
    )

  const compactDecisions =
    currentHumanDecisions.length > 0
      ? currentHumanDecisions.slice(0, 4)
      : decisions.slice(0, 4)

  const visibleDecisions =
    showAllDecisions
      ? decisions
      : compactDecisions

  const visibleDataOpsRuns =
    showAllDataOpsRuns
      ? dataOps?.runs ?? []
      : (dataOps?.runs ?? []).slice(0, 3)

  const visibleQuarantine =
    showAllQuarantine
      ? dataOps?.quarantine ?? []
      : (dataOps?.quarantine ?? []).slice(0, 2)


  const selectedCopilotRun =
    selectedCopilot?.source_entity_id
      ? (
          dataOps?.runs ?? []
        ).find(
          (run) =>
            run.run_id ===
            selectedCopilot.source_entity_id,
        ) ?? null
      : null


  const powerBiReportUrl =
    (
      import.meta.env.VITE_POWER_BI_REPORT_URL ??
      ''
    ).trim()

  return (
    <section
      id="operations-control-tower"
      className="content-card ct-shell"
    >
      <div className="ct-main-header">
        <div>
          <div className="eyebrow">
            Operations Control Tower
          </div>

          <h2>
            Centro de Operaciones y
            Trazabilidad
          </h2>

          <p className="subtle ct-intro">
            Supervisa el estado del sistema,
            sigue el recorrido de las
            operaciones, revisa decisiones
            administrativas y valida la
            calidad de los datos publicados.
          </p>
        </div>

        <div className="ct-main-actions">
          {powerBiReportUrl && (
            <a
              className="secondary-button"
              href={powerBiReportUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              Abrir análisis en Power BI
            </a>
          )}

          {towerOpen && (
            <button
              type="button"
              className="secondary-button"
              disabled={
                loading ||
                actionRunning !== null
              }
              onClick={() =>
                void refreshAll()
              }
            >
              {loading
                ? 'Actualizando…'
                : 'Actualizar estado'}
            </button>
          )}

          <button
            type="button"
            className="ct-collapse-button"
            aria-expanded={towerOpen}
            onClick={() =>
              setTowerOpen(
                (current) => !current,
              )
            }
          >
            <span>
              {towerOpen
                ? 'Ocultar panel'
                : 'Mostrar panel'}
            </span>

            <span
              className={
                towerOpen
                  ? 'ct-section-chevron open'
                  : 'ct-section-chevron'
              }
              aria-hidden="true"
            />
          </button>
        </div>
      </div>


      {error && (
        <div className="message error ct-message">
          {error}
        </div>
      )}


      {towerOpen && (
        <>
          {loading && !overview ? (
            <p className="subtle ct-loading">
              Cargando estado operacional…
            </p>
          ) : (
            <>
              <div className="ct-health-grid">
                <div className="ct-health-card">
                  <span>
                    Servicios bancarios (API)
                  </span>

                  <div className="ct-health-value">
                    <strong>
                      {ctLabel(
                        overview?.api ?? '—',
                      )}
                    </strong>

                    <CtStatus
                      value={
                        overview?.api ?? null
                      }
                    />
                  </div>

                  <small>
                    Servicios disponibles para
                    la aplicación
                  </small>
                </div>


                <div className="ct-health-card">
                  <span>
                    Base transaccional (OLTP)
                  </span>

                  <div className="ct-health-value">
                    <strong>
                      {ctLabel(
                        overview?.postgresql ??
                          '—',
                      )}
                    </strong>

                    <CtStatus
                      value={
                        overview?.postgresql ??
                        null
                      }
                    />
                  </div>

                  <small>
                    Registro de operaciones
                    bancarias
                  </small>
                </div>


                <div className="ct-health-card">
                  <span>
                    Último proceso de datos
                  </span>

                  <div className="ct-health-value">
                    <strong>
                      {latestRun?.status ===
                      'QUALITY_GATE_FAILED'
                        ? 'Requiere revisión'
                        : ctLabel(
                            latestRun?.status ?? '—',
                          )}
                    </strong>

                    <CtStatus
                      value={
                        latestRun?.status ?? null
                      }
                    />
                  </div>

                  <small>
                    {latestRun
                      ? `${latestRun.quality_passed}/${latestRun.quality_total} controles de calidad aprobados`
                      : 'Sin ejecución registrada'}
                  </small>
                </div>


                <div className="ct-health-card">
                  <span>
                    Datos Gold vigentes
                  </span>

                  <div className="ct-health-value">
                    <strong>
                      {ctLabel(
                        currentGold
                          ?.publication_status ??
                          '—',
                      )}
                    </strong>

                    <CtStatus
                      value={
                        currentGold
                          ?.publication_status ??
                        null
                      }
                    />
                  </div>

                  <small>
                    {currentGold
                      ? `${currentGold.quality_gate_passed}/${currentGold.quality_gate_total} controles de calidad aprobados`
                      : 'Sin datos publicados'}
                  </small>
                </div>
              </div>


              <div
                className={
                  protectedGold
                    ? 'ct-resilience-banner protected'
                    : 'ct-resilience-banner'
                }
              >
                <div>
                  <span className="ct-resilience-kicker">
                    Protección de datos
                  </span>

                  <strong>
                    {protectedGold
                      ? 'Última versión confiable protegida'
                      : 'Estado de los datos publicados'}
                  </strong>
                </div>

                <p>
                  {protectedGold
                    ? `La ejecución más reciente aprobó ${latestRun?.quality_passed} de ${latestRun?.quality_total} controles, por lo que no reemplazó los datos Gold vigentes. La versión anterior continúa publicada con ${currentGold?.quality_gate_passed} de ${currentGold?.quality_gate_total} controles aprobados.`
                    : currentGold
                      ? 'La versión Gold vigente superó sus controles y continúa disponible para análisis y reportes.'
                      : 'Actualmente no existe una versión Gold publicada.'}
                </p>
              </div>


              <div className="ct-count-grid">
                <div>
                  <span>
                    Operaciones
                  </span>

                  <strong>
                    {overview?.counts
                      .banking_operations ?? 0}
                  </strong>
                </div>

                <div>
                  <span>
                    Movimientos
                  </span>

                  <strong>
                    {overview?.counts
                      .transactions ?? 0}
                  </strong>
                </div>

                <div>
                  <span>
                    Asientos contables
                  </span>

                  <strong>
                    {overview?.counts
                      .ledger_entries ?? 0}
                  </strong>
                </div>

                <div>
                  <span>
                    Registros de auditoría
                  </span>

                  <strong>
                    {overview?.counts
                      .audit_events ?? 0}
                  </strong>
                </div>

                <div>
                  <span>
                    Aislados históricos
                  </span>

                  <strong>
                    {overview?.counts
                      .quarantine_records ?? 0}
                  </strong>
                </div>
              </div>


              <div className="ct-accordions">
                <section className="ct-accordion">
                  <AccordionHeader
                    eyebrow="Trazabilidad operacional"
                    title="Trazabilidad de operaciones"
                    description="Consulta el recorrido de una operación desde su registro hasta sus movimientos, asientos contables y auditoría."
                    open={operationsOpen}
                    onToggle={() =>
                      setOperationsOpen(
                        (current) =>
                          !current,
                      )
                    }
                  />


                  {operationsOpen && (
                    <div className="ct-accordion-body">
                      <FlowStrip
                        items={[
                          'Operación',
                          'Movimientos',
                          'Asientos contables',
                          'Auditoría',
                        ]}
                      />


                      <div className="ct-subsection-head">
                        <div>
                          <h4>
                            Operaciones recientes
                          </h4>

                          <p>
                            Selecciona una operación
                            para revisar su
                            trazabilidad completa.
                          </p>
                        </div>
                      </div>


                      <div className="ct-table-wrap">
                        <table className="ct-table">
                          <thead>
                            <tr>
                              <th>
                                Operación
                              </th>

                              <th>
                                Responsable
                              </th>

                              <th>
                                Monto
                              </th>

                              <th>
                                Mov.
                              </th>

                              <th>
                                Asientos
                              </th>

                              <th>
                                Estado
                              </th>

                              <th />
                            </tr>
                          </thead>

                          <tbody>
                            {operations.map(
                              (operation) => (
                                <tr
                                  key={
                                    operation.operation_id
                                  }
                                  className={
                                    selectedOperationId ===
                                    operation.operation_id
                                      ? 'ct-selected-row'
                                      : ''
                                  }
                                >
                                  <td>
                                    <strong>
                                      {ctLabel(
                                        operation.operation_type,
                                      )}
                                    </strong>

                                    <span className="ct-operation-id">
                                      ID:{' '}
                                      {ctShort(
                                        operation.operation_id,
                                      )}
                                    </span>
                                  </td>

                                  <td>
                                    {operation.actor_email ??
                                      ctLabel(operation.actor_type)}
                                  </td>

                                  <td>
                                    {ctMoney(
                                      operation.amount,
                                      operation.currency,
                                    )}
                                  </td>

                                  <td>
                                    {
                                      operation.transaction_count
                                    }
                                  </td>

                                  <td>
                                    {
                                      operation.ledger_entry_count
                                    }
                                  </td>

                                  <td>
                                    <CtStatus
                                      value={
                                        operation.status
                                      }
                                    />
                                  </td>

                                  <td>
                                    <button
                                      type="button"
                                      className="secondary-button compact"
                                      onClick={() =>
                                        void toggleTrace(
                                          operation.operation_id,
                                        )
                                      }
                                    >
                                      {selectedOperationId ===
                                      operation.operation_id
                                        ? 'Cerrar'
                                        : 'Ver detalle'}
                                    </button>
                                  </td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>


                      {selectedOperationId && (
                        <div className="ct-trace-panel">
                          {traceLoading ||
                          !trace ? (
                            <p className="subtle">
                              Cargando detalle de
                              trazabilidad…
                            </p>
                          ) : (
                            <>
                              <div className="ct-trace-head">
                                <div>
                                  <span className="ct-section-kicker">
                                    Detalle de
                                    trazabilidad
                                  </span>

                                  <h3>
                                    {ctLabel(
                                      trace.operation
                                        .operation_type,
                                    )}
                                    {' · '}
                                    {ctMoney(
                                      trace.operation
                                        .amount,
                                      trace.operation
                                        .currency,
                                    )}
                                  </h3>
                                </div>

                                <div className="ct-trace-head-actions">
                                  <CtStatus
                                    value={
                                      trace.operation
                                        .status
                                    }
                                  />

                                  <button
                                    type="button"
                                    className="ct-close-detail"
                                    onClick={
                                      closeTrace
                                    }
                                  >
                                    Cerrar detalle
                                  </button>
                                </div>
                              </div>


                              <div className="ct-trace-identity">
                                <div>
                                  <span>
                                    Identificador
                                    de operación
                                  </span>

                                  <code>
                                    {
                                      trace
                                        .operation
                                        .operation_id
                                    }
                                  </code>

                                  <small>
                                    Código único
                                    que permite
                                    seguir esta
                                    operación.
                                  </small>
                                </div>

                                <div>
                                  <span>
                                    Clave
                                    anti-duplicados
                                  </span>

                                  <code>
                                    {
                                      trace
                                        .operation
                                        .idempotency_key
                                    }
                                  </code>

                                  <small>
                                    Evita que una
                                    misma solicitud
                                    se procese más de
                                    una vez.
                                  </small>
                                </div>
                              </div>


                              <div className="ct-trace-grid">
                                <div className="ct-trace-card">
                                  <span className="ct-trace-title">
                                    Movimientos de
                                    cuenta
                                  </span>

                                  {trace.transactions.map(
                                    (item) => (
                                      <div
                                        className="ct-trace-row"
                                        key={
                                          item.transaction_id
                                        }
                                      >
                                        <div>
                                          <strong>
                                            {ctLabel(
                                              item.transaction_type,
                                            )}
                                          </strong>

                                          <span>
                                            Cuenta
                                            terminada
                                            en{' '}
                                            {item.account_last4 ??
                                              '—'}
                                          </span>

                                          {item.loan_id && (
                                            <span>
                                              Préstamo vinculado:{' '}
                                              {ctShort(item.loan_id)}
                                            </span>
                                          )}
                                        </div>

                                        <div className="ct-trace-value">
                                          <CtStatus
                                            value={
                                              item.direction
                                            }
                                          />

                                          <strong>
                                            {ctMoney(
                                              item.amount,
                                              item.currency,
                                            )}
                                          </strong>
                                        </div>
                                      </div>
                                    ),
                                  )}
                                </div>


                                <div className="ct-trace-card">
                                  <div className="ct-trace-section-heading">
                                    <span className="ct-trace-title">
                                      Asientos contables
                                    </span>

                                    <small>
                                      Registros de cargo y abono que mantienen
                                      equilibrada la operación.
                                    </small>
                                  </div>

                                  {trace.ledger.map(
                                    (item) => (
                                      <div
                                        className="ct-trace-row"
                                        key={
                                          item.ledger_entry_id
                                        }
                                      >
                                        <div>
                                          <strong>
                                            Registro contable{' '}
                                            {
                                              item.sequence_no
                                            }
                                          </strong>

                                          <span>
                                            {ctLedgerAccount(
                                              item.account_id,
                                              item.clearing_account_code,
                                            )}
                                          </span>
                                        </div>

                                        <div className="ct-trace-value">
                                          <CtStatus
                                            value={
                                              item.direction
                                            }
                                          />

                                          <strong>
                                            {ctMoney(
                                              item.amount,
                                              item.currency,
                                            )}
                                          </strong>
                                        </div>
                                      </div>
                                    ),
                                  )}
                                </div>
                              </div>


                              <div className="ct-audit-card">
                                <span className="ct-trace-title">
                                  Registro de
                                  auditoría
                                </span>

                                {trace.audit.map(
                                  (event) => (
                                    <div
                                      className="ct-audit-row"
                                      key={
                                        event.audit_event_id
                                      }
                                    >
                                      <div>
                                        <strong>
                                          {ctLabel(
                                            event.action,
                                          )}
                                        </strong>

                                        <span>
                                          Responsable:{' '}
                                          {event.actor_email ??
                                            ctLabel(
                                              event.actor_type,
                                            )}
                                        </span>

                                        {ctAuditTransferSummary(event) && (
                                          <span>
                                            {ctAuditTransferSummary(event)}
                                          </span>
                                        )}
                                      </div>

                                      <div>
                                        <CtStatus
                                          value={
                                            event.result
                                          }
                                        />

                                        <span className="ct-correlation-label">
                                          Referencia:{' '}
                                          {ctShort(
                                            event.correlation_id,
                                          )}
                                        </span>
                                      </div>
                                    </div>
                                  ),
                                )}
                              </div>


                              <div
                                className={
                                  trace.lineage
                                    ? 'ct-lineage-card available'
                                    : 'ct-lineage-card pending'
                                }
                              >
                                <span className="ct-trace-title">
                                  Recorrido hacia
                                  analítica
                                </span>

                                {trace.lineage ? (
                                  <>
                                    <p className="ct-lineage-description">
                                      La operación
                                      ya fue
                                      incorporada
                                      al almacén
                                      analítico y
                                      puede
                                      relacionarse
                                      con la
                                      ejecución de
                                      datos que la
                                      procesó.
                                    </p>

                                    <div className="ct-lineage-flow">
                                      <div>
                                        <span>
                                          Operación
                                        </span>

                                        <strong>
                                          {ctShort(
                                            trace
                                              .operation
                                              .operation_id,
                                          )}
                                        </strong>
                                      </div>

                                      <span>
                                        →
                                      </span>

                                      <div>
                                        <span>
                                          Ejecución
                                          de datos
                                        </span>

                                        <strong>
                                          {ctShort(
                                            trace
                                              .lineage
                                              .last_run_id,
                                          )}
                                        </strong>
                                      </div>

                                      <span>
                                        →
                                      </span>

                                      <div>
                                        <span>
                                          Lote
                                          publicado
                                        </span>

                                        <strong>
                                          {ctShort(
                                            trace
                                              .lineage
                                              .batch_id,
                                          )}
                                        </strong>
                                      </div>

                                      <span>
                                        →
                                      </span>

                                      <div>
                                        <span>
                                          Gold
                                        </span>

                                        <CtStatus
                                          value={
                                            trace
                                              .lineage
                                              .publication_status
                                          }
                                        />
                                      </div>
                                    </div>
                                  </>
                                ) : (
                                  <div className="ct-lineage-pending">
                                    <strong>
                                      Pendiente de
                                      incorporación
                                      analítica
                                    </strong>

                                    <p>
                                      La operación
                                      ya está
                                      registrada en
                                      el sistema
                                      transaccional,
                                      pero todavía no
                                      ha sido
                                      incorporada al
                                      almacén
                                      analítico. Una
                                      próxima
                                      ejecución del
                                      proceso de
                                      datos la
                                      integrará a la
                                      capa Gold.
                                    </p>
                                  </div>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </section>


                <section className="ct-accordion">
                  <AccordionHeader
                    eyebrow="Revisión humana"
                    title="Decisiones administrativas"
                    description="Consulta quién tomó cada decisión de identidad o crédito y qué resultado quedó registrado."
                    open={decisionsOpen}
                    onToggle={() =>
                      setDecisionsOpen(
                        (current) =>
                          !current,
                      )
                    }
                  />


                  {decisionsOpen && (
                    <div className="ct-accordion-body">
                      <div className="ct-decision-list">
                        {visibleDecisions.map(
                          (decision) => (
                            <article
                              className="ct-decision-card"
                              key={
                                decision.audit_event_id
                              }
                            >
                              <div className="ct-decision-main">
                                <div>
                                  <span className="ct-decision-type">
                                    {ctLabel(
                                      decision.action,
                                    )}
                                  </span>

                                  <strong>
                                    {decision.subject_name ??
                                      'Registro administrativo'}
                                  </strong>

                                  <small>
                                    Código de
                                    cliente:{' '}
                                    {decision.subject_code ??
                                      '—'}
                                  </small>
                                </div>

                                <CtStatus
                                  value={
                                    decision.decision
                                  }
                                />
                              </div>


                              <div className="ct-decision-meta">
                                <div>
                                  <span>
                                    Revisor
                                  </span>

                                  <strong>
                                    {decision.reviewer_email ??
                                      '—'}
                                  </strong>
                                </div>

                                <div>
                                  <span>
                                    Rol
                                  </span>

                                  <strong>
                                    {ctLabel(
                                      decision.reviewer_role,
                                    )}
                                  </strong>
                                </div>

                                <div>
                                  <span>
                                    Fecha
                                  </span>

                                  <strong>
                                    {ctDate(
                                      decision.occurred_at,
                                    )}
                                  </strong>
                                </div>

                                <div>
                                  <span>
                                    Decisión humana
                                  </span>

                                  <strong>
                                    {decision.human_decision ===
                                    'true'
                                      ? 'Sí'
                                      : 'Registro histórico'}
                                  </strong>
                                </div>
                              </div>


                              {decision.action ===
                                'LOAN_APPLICATION_REVIEW' && (
                                <div className="ct-decision-evidence">
                                  <span>
                                    Tasa anual
                                    efectiva:
                                  </span>

                                  <strong>
                                    {decision.tea_percent
                                      ? ` ${decision.tea_percent}%`
                                      : ' —'}
                                  </strong>

                                  <span className="ct-divider">
                                    ·
                                  </span>

                                  <span>
                                    Decisión
                                    automática por
                                    IA:
                                  </span>

                                  <strong>
                                    {decision.llm_decision ===
                                    'true'
                                      ? ' Sí'
                                      : ' No'}
                                  </strong>

                                  {decision.disbursement_status && (
                                    <>
                                      <span className="ct-divider">
                                        ·
                                      </span>

                                      <span>
                                        Desembolso:
                                      </span>

                                      <strong>
                                        {' '}
                                        {ctLabel(decision.disbursement_status)}
                                      </strong>

                                      {decision.scheduled_disbursement_at && (
                                        <>
                                          <span className="ct-divider">
                                            ·
                                          </span>
                                          <span>
                                            Fecha prevista:
                                          </span>
                                          <strong>
                                            {' '}
                                            {ctDate(decision.scheduled_disbursement_at)}
                                          </strong>
                                        </>
                                      )}
                                    </>
                                  )}
                                </div>
                              )}


                              {decision.action ===
                                'SYNTHETIC_ONBOARDING_REVIEW' &&
                                decision.evidence_ref && (
                                  <div className="ct-decision-evidence">
                                    <span>
                                      Referencia de
                                      evidencia:
                                    </span>

                                    <code>
                                      {
                                        decision.evidence_ref
                                      }
                                    </code>

                                    {decision.reniec_result && (
                                      <>
                                        <span className="ct-divider">
                                          ·
                                        </span>

                                        <span>
                                          Verificación
                                          de identidad:
                                        </span>

                                        <strong>
                                          {' '}
                                          {ctLabel(
                                            decision.reniec_result,
                                          )}
                                        </strong>
                                      </>
                                    )}
                                  </div>
                                )}
                            </article>
                          ),
                        )}
                      </div>


                      {decisions.length >
                        compactDecisions.length && (
                        <button
                          type="button"
                          className="ct-history-button"
                          onClick={() =>
                            setShowAllDecisions(
                              (current) =>
                                !current,
                            )
                          }
                        >
                          {showAllDecisions
                            ? 'Mostrar solo decisiones recientes'
                            : `Ver historial completo (${decisions.length})`}
                        </button>
                      )}
                    </div>
                  )}
                </section>


                <section className="ct-accordion">
                  <AccordionHeader
                    eyebrow="DataOps"
                    title="Calidad y publicación de datos"
                    description="Revisa las ejecuciones del proceso de datos, sus controles de calidad, los registros aislados y la versión Gold vigente."
                    open={dataOpsOpen}
                    onToggle={() =>
                      setDataOpsOpen(
                        (current) =>
                          !current,
                      )
                    }
                  />


                  {dataOpsOpen && (
                    <div className="ct-accordion-body">
                      <FlowStrip
                        items={[
                          'Datos operativos',
                          'Preparación (Bronze / Silver)',
                          'Controles de calidad',
                          'Gold / Registros aislados',
                        ]}
                      />

                      <div className="ct-admin-actions-card">
                        <div className="ct-admin-action-copy">
                          <span className="ct-section-kicker">
                            Acciones administrativas
                          </span>

                          <h4>
                            Gestión del proceso de datos
                          </h4>

                          <p>
                            Ejecuta el procesamiento normal de datos
                            o valida la protección de Gold mediante
                            una prueba controlada de calidad.
                          </p>
                        </div>

                        <div className="ct-admin-action-buttons">
                          <button
                            type="button"
                            className="primary-button"
                            disabled={
                              actionRunning !== null ||
                              loading
                            }
                            onClick={() => {
                              setActionNotice(null)
                              setPendingAction('DATAOPS')
                            }}
                          >
                            {actionRunning === 'DATAOPS'
                              ? 'Procesando…'
                              : 'Ejecutar proceso de datos'}
                          </button>

                          <button
                            type="button"
                            className="secondary-button"
                            disabled={
                              actionRunning !== null ||
                              loading
                            }
                            onClick={() => {
                              setActionNotice(null)
                              setPendingAction('QUALITY')
                            }}
                          >
                            {actionRunning === 'QUALITY'
                              ? 'Ejecutando prueba…'
                              : 'Probar control de calidad'}
                          </button>
                        </div>
                      </div>


                      {pendingAction && (
                        <div
                          className={
                            pendingAction === 'QUALITY'
                              ? 'ct-action-confirm warning'
                              : 'ct-action-confirm'
                          }
                        >
                          <div>
                            <strong>
                              {pendingAction === 'DATAOPS'
                                ? '¿Ejecutar el proceso de datos?'
                                : '¿Ejecutar la prueba controlada?'}
                            </strong>

                            <p>
                              {pendingAction === 'DATAOPS'
                                ? (
                                    'Se procesarán los datos operativos, ' +
                                    'se evaluarán los controles de calidad ' +
                                    'y, si todos son aprobados, se publicará ' +
                                    'una nueva versión Gold.'
                                  )
                                : (
                                    'Se incorporará temporalmente un registro ' +
                                    'inválido únicamente durante esta ejecución. ' +
                                    'El objetivo es comprobar que el dato sea ' +
                                    'aislado y que una versión Gold válida no sea reemplazada.'
                                  )}
                            </p>
                          </div>

                          <div className="ct-action-confirm-buttons">
                            <button
                              type="button"
                              className="secondary-button compact"
                              onClick={() =>
                                setPendingAction(null)
                              }
                            >
                              Cancelar
                            </button>

                            <button
                              type="button"
                              className="primary-button compact"
                              onClick={() => {
                                if (pendingAction) {
                                  void executeAdminAction(
                                    pendingAction,
                                  )
                                }
                              }}
                            >
                              Confirmar ejecución
                            </button>
                          </div>
                        </div>
                      )}


                      {actionNotice && (
                        <div
                          className={`ct-action-notice ${actionNotice.tone}`}
                        >
                          <strong>
                            {actionNotice.tone === 'success'
                              ? 'Proceso completado'
                              : 'Protección validada'}
                          </strong>

                          <p>
                            {actionNotice.text}
                          </p>
                        </div>
                      )}


                      <div className="ct-subsection-head">
                        <div>
                          <h4>
                            Ejecuciones del
                            proceso de datos
                          </h4>

                          <p>
                            Cada ejecución
                            registra cuántos
                            datos fueron
                            procesados y si
                            superaron los
                            controles de
                            calidad.
                          </p>
                        </div>
                      </div>


                      <div className="ct-table-wrap">
                        <table className="ct-table">
                          <thead>
                            <tr>
                              <th>
                                Ejecución
                              </th>

                              <th>
                                Resultado
                              </th>

                              <th>
                                Registros
                              </th>

                              <th>
                                Controles de
                                calidad
                              </th>

                              <th>
                                Aislados
                              </th>

                              <th>
                                Gold
                              </th>

                              <th>
                                Copilot
                              </th>
                            </tr>
                          </thead>

                          <tbody>
                            {visibleDataOpsRuns.map(
                              (run) => (
                                <tr
                                  key={
                                    run.run_id
                                  }
                                >
                                  <td>
                                    <strong>
                                      ID:{' '}
                                      {ctShort(
                                        run.run_id,
                                      )}
                                    </strong>

                                    <span>
                                      {ctDate(
                                        run.started_at,
                                      )}
                                    </span>
                                  </td>

                                  <td>
                                    <CtStatus
                                      value={
                                        run.status
                                      }
                                    />
                                  </td>

                                  <td>
                                    {
                                      run.rows_accepted
                                    }
                                    /
                                    {
                                      run.rows_extracted
                                    }
                                  </td>

                                  <td>
                                    {
                                      run.quality_passed
                                    }
                                    /
                                    {
                                      run.quality_total
                                    }
                                  </td>

                                  <td>
                                    {
                                      run.quarantine_records
                                    }
                                  </td>

                                  <td>
                                    {run.is_current_gold ? (
                                      <CtStatus
                                        value="PUBLISHED"
                                      />
                                    ) : (
                                      '—'
                                    )}
                                  </td>


                                  <td className="ct-copilot-action-cell">
                                    {(
                                      run.status !==
                                        'SUCCEEDED' ||
                                      run.quality_failed >
                                        0 ||
                                      run.quarantine_records >
                                        0
                                    ) ? (
                                      <button
                                        type="button"
                                        className="secondary-button compact"
                                        disabled={
                                          copilotLoadingRunId !==
                                            null ||
                                          actionRunning !==
                                            null
                                        }
                                        onClick={() =>
                                          void toggleCopilot(
                                            run.run_id,
                                          )
                                        }
                                      >
                                        {copilotLoadingRunId ===
                                        run.run_id
                                          ? 'Analizando...'
                                          : selectedCopilot
                                                ?.source_entity_id ===
                                              run.run_id
                                            ? 'Cerrar análisis'
                                            : copilotHistory.some(
                                                  (
                                                    item,
                                                  ) =>
                                                    item.source_entity_id ===
                                                    run.run_id,
                                                )
                                              ? 'Ver análisis'
                                              : 'Analizar con IA'}
                                      </button>
                                    ) : (
                                      <button
                                        type="button"
                                        className="secondary-button compact ct-copilot-na-button"
                                        disabled
                                        title="No requiere análisis: ejecución correcta"
                                      >
                                        No aplica
                                      </button>
                                    )}
                                  </td>                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>

                        {(dataOps?.runs.length ?? 0) > 3 && (
                          <div className="ct-show-more-row ct-show-more-runs">
                            <span>
                              Mostrando{' '}
                              {visibleDataOpsRuns.length} de{' '}
                              {dataOps?.runs.length ?? 0}{' '}
                              ejecuciones recientes
                            </span>

                            <button
                              type="button"
                              className="ct-show-more-button"
                              onClick={() =>
                                setShowAllDataOpsRuns(
                                  (current) => !current,
                                )
                              }
                            >
                              {showAllDataOpsRuns
                                ? 'Ver menos'
                                : 'Ver más'}
                            </button>
                          </div>
                        )}
                      </div>

                      {selectedCopilot && (
                        <div className="ct-trace-panel ct-copilot-panel">
                          <div className="ct-trace-head">
                            <div>
                              <span className="ct-section-kicker">
                                BancoCloud Operational Copilot
                              </span>

                              <h3>
                                Análisis asistido de la incidencia
                              </h3>
                            </div>

                            <div className="ct-trace-head-actions">
                              <CtStatus
                                value={
                                  selectedCopilot
                                    .human_review_status
                                }
                              />

                              <button
                                type="button"
                                className="ct-close-detail"
                                onClick={() =>
                                  setSelectedCopilot(
                                    null,
                                  )
                                }
                              >
                                Cerrar detalle
                              </button>
                            </div>
                          </div>


                          <div className="ct-trace-identity">
                            <div>
                              <span>
                                Ejecución analizada
                              </span>

                              <code>
                                {
                                  selectedCopilot
                                    .source_entity_id
                                }
                              </code>

                              <small>
                                Ejecución con un problema de calidad revisada por el Copilot.
                              </small>
                            </div>

                            <div>
                              <span>
                                Referencia de seguimiento
                              </span>

                              <code>
                                {
                                  selectedCopilot
                                    .correlation_id
                                }
                              </code>

                              <small>
                                Conecta el análisis, la auditoría y la revisión humana.
                              </small>
                            </div>
                          </div>


                          <div className="ct-decision-meta">
                            <div>
                              <span>
                                Modelo
                              </span>

                              <strong>
                                {selectedCopilot.model ??
                                  '?'}
                              </strong>
                            </div>

                            <div>
                              <span>
                                Versión del prompt
                              </span>

                              <strong>
                                {
                                  selectedCopilot
                                    .prompt_version ??
                                  '?'
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Categoría
                              </span>

                              <strong>
                                {ctLabel(
                                  selectedCopilot
                                    .category,
                                )}
                              </strong>
                            </div>

                            <div>
                              <span>
                                Confianza
                              </span>

                              <strong>
                                {selectedCopilot
                                  .confidence !== null
                                  ? `${Math.round(
                                      selectedCopilot
                                        .confidence *
                                        100,
                                    )}%`
                                  : '?'}
                              </strong>
                            </div>
                          </div>


                          {selectedCopilot.analysis && (
                            <>
                              <div className="ct-trace-card ct-copilot-summary">
                                <span className="ct-trace-title">
                                  Resumen
                                </span>

                                <p>
                                  {selectedCopilotRun ? (
                                    <>
                                      {`La ejecución procesó ${selectedCopilotRun.rows_extracted} registros. `}
                                      {`Aceptados: ${selectedCopilotRun.rows_accepted}. `}
                                      {`Aislados por calidad: ${selectedCopilotRun.rows_quarantined}. `}
                                      {`Controles aprobados: ${selectedCopilotRun.quality_passed} de ${selectedCopilotRun.quality_total}. `}
                                      {selectedCopilotRun.is_current_gold
                                        ? 'Esta ejecución corresponde a la versión Gold vigente.'
                                        : 'La versión Gold vigente se mantuvo protegida y no fue reemplazada por esta ejecución.'}
                                    </>
                                  ) : (
                                    selectedCopilot.analysis.summary
                                  )}
                                </p>
                              </div>


                              <div className="ct-trace-grid">
                                <div className="ct-trace-card">
                                  <span className="ct-trace-title">
                                    Alertas identificadas
                                  </span>

                                  <ul className="ct-copilot-list">
                                    {ctCopilotRiskItems(
                                      selectedCopilot.analysis.risk_flags,
                                      selectedCopilotRun,
                                    ).map(
                                      (item, index) => (
                                        <li
                                          key={`${item}-${index}`}
                                        >
                                          {item}
                                        </li>
                                      ),
                                    )}
                                  </ul>
                                </div>


                                <div className="ct-trace-card">
                                  <span className="ct-trace-title">
                                    Información por verificar
                                  </span>

                                  <ul className="ct-copilot-list">
                                    {ctCopilotPendingItems(
                                      selectedCopilot.analysis.missing_information,
                                    ).map(
                                      (item, index) => (
                                        <li
                                          key={`${item}-${index}`}
                                        >
                                          {item}
                                        </li>
                                      ),
                                    )}
                                  </ul>
                                </div>
                              </div>


                              <div className="ct-audit-card ct-copilot-next-step">
                                <span className="ct-trace-title">
                                  Siguiente paso recomendado
                                </span>

                                <p>
                                  {
                                    ctCopilotNextStep(
                                    selectedCopilot.analysis.recommended_next_step,
                                  )
                                  }
                                </p>
                              </div>


                              <div className="ct-audit-card ct-copilot-evidence">
                                <span className="ct-trace-title">
                                  Evidencia técnica utilizada
                                </span>

                                <ul className="ct-copilot-list">
                                  {selectedCopilot.analysis.evidence.map(
                                    (
                                      item,
                                      index,
                                    ) => (
                                      <li
                                        key={`${item}-${index}`}
                                      >
                                        {item}
                                      </li>
                                    ),
                                  )}
                                </ul>
                              </div>
                            </>
                          )}


                          {selectedCopilot
                            .human_review_status ===
                          'COMPLETED' ? (
                            <div className="ct-action-notice success ct-copilot-review">
                              <strong>
                                Revisión humana completada
                              </strong>

                              <p>
                                Revisor:{' '}
                                {selectedCopilot
                                  .human_review
                                  ?.reviewer_email ??
                                  'administrador'}
                                {' | Estado: '}
                                {ctLabel(
                                  selectedCopilot
                                    .human_review
                                    ?.decision ??
                                    'ACKNOWLEDGED',
                                )}
                                {selectedCopilot
                                  .human_review
                                  ?.reviewed_at
                                  ? ` | Fecha: ${ctDate(
                                      selectedCopilot
                                        .human_review
                                        .reviewed_at,
                                    )}`
                                  : ''}
                              </p>

                              {selectedCopilot
                                .human_review
                                ?.notes && (
                                <p>
                                  Observación:{' '}
                                  {ctCopilotReviewNote(
                                    selectedCopilot
                                      .human_review
                                      ?.notes ??
                                      null,
                                  )}
                                </p>
                              )}
                            </div>
                          ) : (
                            <div className="ct-action-confirm warning ct-copilot-review">
                              <div>
                                <strong>
                                  Supervisión humana requerida
                                </strong>

                                <p>
                                  El Copilot interpreta
                                  evidencia y propone un
                                  siguiente paso, pero no
                                  ejecuta acciones bancarias,
                                  no modifica datos y no toma
                                  decisiones sensibles de
                                  forma autónoma.
                                </p>
                              </div>

                              <div className="ct-action-confirm-buttons">
                                <button
                                  type="button"
                                  className="primary-button compact"
                                  disabled={
                                    copilotReviewing
                                  }
                                  onClick={() =>
                                    void acknowledgeCopilot()
                                  }
                                >
                                  {copilotReviewing
                                    ? 'Registrando...'
                                    : 'Reconocer análisis'}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}


                      {dataOps &&
                        dataOps.quarantine.length > 0 && (
                          <div className="ct-quarantine">
                            <div className="ct-quarantine-head">
                              <span className="ct-section-kicker">
                                Control de calidad
                              </span>

                              <h4>
                                Registros aislados por calidad
                              </h4>

                              <p>
                                Estos registros fueron separados
                                para evitar que datos inválidos
                                lleguen a la versión Gold.
                              </p>
                            </div>

                            {visibleQuarantine.map((item) => (
                              <div
                                className="ct-quarantine-row"
                                key={`${item.run_id}-${item.source_table}-${item.rule_name}`}
                              >
                                <div>
                                  <span>
                                    Origen
                                  </span>

                                  <strong>
                                    {ctSourceName(
                                      item.source_table,
                                    )}
                                  </strong>
                                </div>

                                <div>
                                  <span>
                                    Regla aplicada
                                  </span>

                                  <strong>
                                    {ctRuleName(
                                      item.rule_name,
                                    )}
                                  </strong>
                                </div>

                                <div>
                                  <span>
                                    Motivo
                                  </span>

                                  <strong>
                                    {ctReason(
                                      item.reason,
                                    )}
                                  </strong>
                                </div>

                                <div>
                                  <span>
                                    Registros afectados
                                  </span>

                                  <strong>
                                    {item.rejected_records}
                                  </strong>
                                </div>
                              </div>
                            ))}

                            {dataOps.quarantine.length > 2 && (
                              <div className="ct-show-more-row ct-show-more-quarantine">
                                <span>
                                  Mostrando{' '}
                                  {visibleQuarantine.length} de{' '}
                                  {dataOps.quarantine.length}{' '}
                                  registros históricos
                                </span>

                                <button
                                  type="button"
                                  className="ct-show-more-button ct-show-more-button-danger"
                                  onClick={() =>
                                    setShowAllQuarantine(
                                      (current) => !current,
                                    )
                                  }
                                >
                                  {showAllQuarantine
                                    ? 'Ver menos'
                                    : 'Ver más'}
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}

import type { LoanInstallmentDetail, LoanSummary } from './types'
import { getCustomerLoans, getLoanInstallments } from './api'
import type { PendingLoanApplication } from './types'
import { getPendingLoanApplications, reviewLoanApplication } from './api'
import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  ApiError,
  clearSession,
  createAccount,
  deposit,
  getCards,
  getCurrentUser,
  getCustomer,
  getCustomerAccounts,
  getDatabaseHealth,
  getLoanApplications,
  getMovements,
  getPendingOnboarding,
  hasSession,
  issueCard,
  login,
  registerCustomer,
  resolveBancoCloudBeneficiary,
  reviewOnboarding,
  submitLoanApplication,
  transfer,
  transferInterbank,
  transferToBancoCloudThirdParty,
  verifyIdentity,
  withdraw,
} from './api'
import type {
  Account,
  Card,
  CurrentUser,
  Customer,
  IdentityVerificationResponse,
  LoanApplication,
  Movement,
  PendingOnboarding,
  ThirdPartyBeneficiary,
  TransferScope,
  InterbankBankCode,
} from './types'

import { ControlTower } from './ControlTower'
import { Topbar } from './components/layout/Topbar'
import { Metric } from './components/ui/Metric'
import { StatusPill } from './components/ui/StatusPill'
import { AccountsPane } from './features/accounts/AccountsPane'
import { CardsPane } from './features/cards/CardsPane'
import { ApprovedLoansList } from './features/loans/ApprovedLoansList'
import { LoanApplicationForm } from './features/loans/LoanApplicationForm'
import { LoanApplicationsTable } from './features/loans/LoanApplicationsTable'
import { MovementsPane } from './features/movements/MovementsPane'
import { CustomerOverview } from './pages/customer/CustomerOverview'
import { CustomerTabbar } from './pages/customer/CustomerTabbar'
import type { CustomerTab } from './pages/customer/CustomerTabbar'
import { CustomerWorkspace } from './pages/customer/CustomerWorkspace'
import trazaLogo from './assets/branding/traza-logo.jfif?url'

import './index.css'

type View = 'login' | 'register'


type TransferDraft = {
  scope: TransferScope
  ownTarget: string
  thirdPartyAccountNumber: string
  interbankCci: string
  interbankBank: InterbankBankCode
}

function readableError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Correo o contraseña incorrectos.'
    if (error.status === 403) return `Acceso denegado: ${error.message}`
    if (error.status === 409) return error.message
    if (error.status === 422) return `Datos no válidos: ${error.message}`
    return error.message
  }
  return 'No fue posible completar la solicitud.'
}

function money(value: string | number, currency = 'PEN'): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `${currency} ${value}`
  return new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount)
}

function dateTime(value: string): string {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('es-PE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
}

function newIdempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
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

function AuthBrand() {
  return (
    <div className="auth-brand">
      <img className="auth-brand-logo" src={trazaLogo} alt="TRAZA" />
    </div>
  )
}

function LoginPanel({
  onAuthenticated,
  onRegister,
}: {
  onAuthenticated: (user: CurrentUser) => void
  onRegister: () => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const user = await login(email, password)
      onAuthenticated(user)
    } catch (err) {
      setError(readableError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="auth-card login-card" aria-labelledby="login-title">
      <div className="auth-card-heading">
        <AuthBrand />
        <div className="eyebrow">Acceso seguro</div>
        <h1 id="login-title">Bienvenido a TRAZA</h1>
        <p className="subtle">Ingresa con tu perfil para acceder a las funciones habilitadas.</p>
      </div>

      <form onSubmit={submit} className="form-stack public-auth-form" aria-busy={loading}>
        <label>
          <span>Correo</span>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="correo@dominio.com"
            required
          />
        </label>

        <label>
          <span>Contraseña</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••••••"
            required
          />
        </label>

        {error && <div className="message error" role="alert">{error}</div>}

        <button className="primary-button" type="submit" disabled={loading}>
          {loading ? 'Validando…' : 'Iniciar sesión'}
        </button>
      </form>

      <button className="text-button" type="button" onClick={onRegister}>
        Registrarme
      </button>
    </section>
  )
}

function RegisterPanel({
  onBack,
  onRegistered,
}: {
  onBack: () => void
  onRegistered: (email: string) => void
}) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [region, setRegion] = useState('Lima')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await registerCustomer({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        region: region.trim(),
        password,
      })
      onRegistered(email.trim().toLowerCase())
    } catch (err) {
      setError(readableError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="auth-card wide-card register-card" aria-labelledby="register-title">
      <div className="auth-card-heading">
        <AuthBrand />
        <div className="eyebrow">Registro y verificación digital</div>
        <h1 id="register-title">Crear cliente</h1>
        <p className="subtle">El registro queda Pendiente hasta completar la revisión de identidad.</p>
      </div>

      <form onSubmit={submit} className="form-grid public-auth-form" aria-busy={loading}>
        <label>
          <span>Nombre completo</span>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={3} />
        </label>

        <label>
          <span>Región</span>
          <input value={region} onChange={(e) => setRegion(e.target.value)} required minLength={2} />
        </label>

        <label className="full-width">
          <span>Correo</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>

        <label className="full-width">
          <span>Contraseña</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={12}
            required
          />
          <span className="field-help">12+ caracteres con mayúscula, minúscula, número y símbolo.</span>
        </label>

        {error && <div className="message error full-width" role="alert">{error}</div>}

        <div className="button-row full-width">
          <button type="button" className="secondary-button" onClick={onBack}>
            Volver
          </button>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? 'Registrando…' : 'Registrar cliente'}
          </button>
        </div>
      </form>
    </section>
  )
}

function AdminDashboard({
  user,
  dbStatus,
  pending,
  pendingLoans,
  refresh,
  onLogout,
}: {
  user: CurrentUser
  dbStatus: string
  pending: PendingOnboarding[]
  pendingLoans: PendingLoanApplication[]
  refresh: () => Promise<void>
  onLogout: () => void
}) {
  const [reviewing, setReviewing] = useState<string | null>(null)

  const [decision, setDecision] =
    useState<'VERIFIED' | 'REJECTED'>('VERIFIED')

  const [documentChecked, setDocumentChecked] = useState(true)
  const [dataConsistent, setDataConsistent] = useState(true)

  const [notes, setNotes] = useState(
    'Identidad revisada por el administrador.',
  )

  const [loanReviewing, setLoanReviewing] =
    useState<string | null>(null)

  const [loanDecision, setLoanDecision] =
    useState<'APPROVED' | 'REJECTED'>('APPROVED')

  const [annualRate, setAnnualRate] = useState('18.00')

  const [loanNotes, setLoanNotes] = useState(
    'Revisión crediticia completada por el administrador.',
  )

  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  function toggleIdentityReview(customerId: string) {
    if (reviewing === customerId) {
      setReviewing(null)
      return
    }

    setReviewing(customerId)

    setDecision('VERIFIED')
    setDocumentChecked(true)
    setDataConsistent(true)

    setNotes(
      'Identidad revisada por el administrador.',
    )

    setMessage('')
    setError('')
  }

  function toggleLoanReview(applicationId: string) {
    if (loanReviewing === applicationId) {
      setLoanReviewing(null)
      return
    }

    setLoanReviewing(applicationId)

    setLoanDecision('APPROVED')
    setAnnualRate('18.00')

    setLoanNotes(
      'Revisión crediticia completada por el administrador.',
    )

    setMessage('')
    setError('')
  }

  async function submitReview(
    item: PendingOnboarding,
  ) {
    setBusy(true)
    setMessage('')
    setError('')

    try {
      const verification = item.identity_verification

      if (
        decision === 'VERIFIED' &&
        verification?.result !== 'MATCH'
      ) {
        setError(
          'La identidad debe registrar una coincidencia antes de ser verificada.',
        )
        return
      }

      if (
        decision === 'VERIFIED' &&
        (!documentChecked || !dataConsistent)
      ) {
        setError(
          'Completa los controles de revisión antes de verificar al cliente.',
        )
        return
      }

      const safeCode = item.customer_code.replace(
        /[^A-Za-z0-9_-]/g,
        '_',
      )

      const evidenceRef =
        verification?.evidence_ref ??
        `SIM-ADMIN-${safeCode}`.slice(0, 80)

      await reviewOnboarding(
        item.customer_id,
        {
          decision,
          evidence_ref: evidenceRef,
          document_checked: documentChecked,
          data_consistent: dataConsistent,
          notes: notes.trim(),
        },
      )

      setMessage(
        decision === 'VERIFIED'
          ? `${item.full_name} fue verificado correctamente.`
          : `${item.full_name} fue rechazado. La decisión quedó registrada.`,
      )

      setReviewing(null)

      await refresh()
    } catch (err) {
      setError(readableError(err))
    } finally {
      setBusy(false)
    }
  }

  async function submitLoanReview(
    item: PendingLoanApplication,
  ) {
    setBusy(true)
    setMessage('')
    setError('')

    try {
      let parsedRate: number | null = null

      if (loanDecision === 'APPROVED') {
        const rate = Number(annualRate)

        if (
          !Number.isFinite(rate) ||
          rate <= 0 ||
          rate > 100
        ) {
          setError(
            'La TEA debe ser mayor que 0 y menor o igual que 100.',
          )
          return
        }

        parsedRate = rate
      }

      const result = await reviewLoanApplication(
        item.application_id,
        {
          decision: loanDecision,
          annual_rate: parsedRate,
          notes: loanNotes.trim(),
        },
      )

      if (result.decision === 'APPROVED') {
        setMessage(
          `${item.full_name}: solicitud aprobada. Préstamo creado con ${result.installments_created} cuotas y desembolso programado${
            result.scheduled_disbursement_at
              ? ` para ${dateTime(result.scheduled_disbursement_at)}`
              : ''
          }${
            result.disbursement_account_last4
              ? ` en la cuenta terminada en ${result.disbursement_account_last4}`
              : ''
          }.`,
        )
      } else {
        setMessage(
          `${item.full_name}: solicitud rechazada. La decisión quedó registrada.`,
        )
      }

      setLoanReviewing(null)

      await refresh()
    } catch (err) {
      setError(readableError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell admin-shell">
      <Topbar onLogout={onLogout} />

      <main
        className="dashboard admin-dashboard-main"
        aria-labelledby="admin-dashboard-title"
      >
        <section className="hero-card admin-hero">
          <div>
            <div className="eyebrow">
              Administración TRAZA
            </div>

            <h1 id="admin-dashboard-title">Panel administrativo</h1>

            <p className="subtle">
              Gestión de identidad, aprobaciones y solicitudes crediticias.
            </p>
          </div>

          <div className="hero-status admin-hero-status">
            <span>Base de datos</span>
            <StatusPill value={dbStatus} />
          </div>
        </section>

        <section
          className="metrics-grid four admin-metrics"
          aria-label="Resumen administrativo"
        >
          <Metric
            label="Rol"
            value={uiLabel(user.role)}
            note="Acceso administrativo"
          />

          <Metric
            label="Cuenta"
            value={user.email}
            note="Usuario autenticado"
          />

          <Metric
            label="Identidades pendientes"
            value={String(pending.length)}
            note="Solicitudes por revisar"
          />

          <Metric
            label="Créditos pendientes"
            value={String(pendingLoans.length)}
            note="Solicitudes por revisar"
          />
        </section>

        {message && (
          <div
            className="message success block-gap admin-feedback"
            role="status"
          >
            {message}
          </div>
        )}

        {error && (
          <div
            className="message error block-gap admin-feedback"
            role="alert"
          >
            {error}
          </div>
        )}

        <ControlTower />

        {/* =====================================================
            REVISIÓN DE IDENTIDAD
            ===================================================== */}
        <section
          className="content-card admin-work-section onboarding-review-section"
          aria-labelledby="onboarding-review-title"
        >
          <div className="section-title admin-section-title">
            <div>
              <div className="eyebrow">
                Gestión de identidad
              </div>

              <h2 id="onboarding-review-title">Cola de verificación</h2>
            </div>

            <span
              className="queue-count"
              aria-label={`${pending.length} solicitudes de identidad pendientes`}
            >
              {pending.length}
            </span>
          </div>

          {pending.length === 0 ? (
            <p className="subtle admin-empty-state" role="status">
              No existen solicitudes pendientes.
            </p>
          ) : (
            <div className="queue-list onboarding-queue">
              {pending.map((item) => {
                const verification =
                  item.identity_verification

                const canVerify =
                  verification?.result === 'MATCH' &&
                  documentChecked &&
                  dataConsistent

                return (
                  <div
                    className="review-card admin-review-card"
                    key={item.customer_id}
                  >
                    <div className="queue-row review-summary admin-card-header">
                      <div className="admin-customer-meta">
                        <strong>
                          {item.full_name}
                        </strong>

                        <div className="admin-meta-row">
                          <span className="admin-meta-label">
                            Código cliente
                          </span>

                          <span>
                            {item.customer_code}
                          </span>
                        </div>

                        <div className="admin-meta-row">
                          <span className="admin-meta-label">
                            ID interno
                          </span>

                          <span className="mono">
                            {shortId(item.customer_id)}
                          </span>
                        </div>
                      </div>

                      <div className="row-actions admin-review-actions">
                        <StatusPill
                          value={item.onboarding_status}
                        />

                        <button
                          type="button"
                          className="secondary-button compact"
                          aria-expanded={reviewing === item.customer_id}
                          aria-controls={`identity-review-${item.customer_id}`}
                          onClick={() =>
                            toggleIdentityReview(
                              item.customer_id,
                            )
                          }
                        >
                          {reviewing === item.customer_id
                            ? 'Cerrar'
                            : 'Revisar'}
                        </button>
                      </div>
                    </div>

                    <div
                      className="admin-identity-summary reniec-review-summary"
                      aria-label="Resultado RENIEC Simulator"
                    >
                      <div>
                        <span className="field-help">
                          Validación de identidad
                        </span>

                        {verification ? (
                          <StatusPill
                            value={verification.result}
                          />
                        ) : (
                          <span className="subtle">
                            Pendiente de validación
                          </span>
                        )}
                      </div>

                      <div>
                        <span className="field-help">
                          Referencia de evidencia
                        </span>

                        <span className="mono">
                          {verification?.evidence_ref ?? '—'}
                        </span>
                      </div>

                      <div>
                        <span className="field-help">
                          Fecha de validación
                        </span>

                        <span>
                          {verification
                            ? dateTime(
                                verification.verified_at,
                              )
                            : '—'}
                        </span>
                      </div>

                      <div>
                        <span className="field-help">
                          Fuente
                        </span>

                        <span>
                          {verification
                            ? 'RENIEC Simulator'
                            : '—'}
                        </span>
                      </div>
                    </div>

                    {reviewing === item.customer_id && (
                      <div
                        id={`identity-review-${item.customer_id}`}
                        className="review-form admin-review-form"
                        aria-busy={busy}
                      >
                        <div className="decision-block">
                          <span className="field-help">
                            Decisión administrativa
                          </span>

                          <div
                            className="decision-buttons"
                            role="group"
                            aria-label="Decisión administrativa"
                          >
                            <button
                              type="button"
                              aria-pressed={
                                decision === 'VERIFIED'
                              }
                              className={
                                decision === 'VERIFIED'
                                  ? 'decision-option approve selected'
                                  : 'decision-option approve'
                              }
                              onClick={() =>
                                setDecision('VERIFIED')
                              }
                            >
                              Verificar
                            </button>

                            <button
                              type="button"
                              aria-pressed={
                                decision === 'REJECTED'
                              }
                              className={
                                decision === 'REJECTED'
                                  ? 'decision-option reject selected'
                                  : 'decision-option reject'
                              }
                              onClick={() =>
                                setDecision('REJECTED')
                              }
                            >
                              Rechazar
                            </button>
                          </div>
                        </div>

                        {decision === 'VERIFIED' && (
                          <div className="review-checks">
                            <label
                              className={
                                documentChecked
                                  ? 'review-check checked'
                                  : 'review-check'
                              }
                            >
                              <input
                                type="checkbox"
                                checked={documentChecked}
                                onChange={(e) =>
                                  setDocumentChecked(
                                    e.target.checked,
                                  )
                                }
                              />

                              <span className="review-check-copy">
                                <strong>
                                  Documento revisado
                                </strong>

                                <small>
                                  Se revisó la evidencia presentada.
                                </small>
                              </span>
                            </label>

                            <label
                              className={
                                dataConsistent
                                  ? 'review-check checked'
                                  : 'review-check'
                              }
                            >
                              <input
                                type="checkbox"
                                checked={dataConsistent}
                                onChange={(e) =>
                                  setDataConsistent(
                                    e.target.checked,
                                  )
                                }
                              />

                              <span className="review-check-copy">
                                <strong>
                                  Información consistente
                                </strong>

                                <small>
                                  Los datos concuerdan con la validación registrada.
                                </small>
                              </span>
                            </label>
                          </div>
                        )}

                        <label className="admin-notes-field">
                          Notas

                          <textarea
                            value={notes}
                            onChange={(e) =>
                              setNotes(e.target.value)
                            }
                            maxLength={250}
                          />
                        </label>

                        {decision === 'VERIFIED' &&
                          verification?.result !== 'MATCH' && (
                            <div className="review-guidance warning" role="note">
                              La aprobación estará disponible cuando la
                              validación de identidad registre una
                              coincidencia.
                            </div>
                          )}

                        {decision === 'VERIFIED' &&
                          verification?.result === 'MATCH' &&
                          (!documentChecked ||
                            !dataConsistent) && (
                            <div className="review-guidance warning" role="note">
                              Completa los controles de revisión para
                              continuar.
                            </div>
                          )}

                        {decision === 'REJECTED' && (
                          <div className="review-guidance danger" role="note">
                            El rechazo impedirá habilitar los productos
                            bancarios de esta solicitud.
                          </div>
                        )}

                        <div className="button-row admin-submit-row">
                          <button
                            type="button"
                            className={
                              decision === 'VERIFIED'
                                ? 'admin-submit approve-submit'
                                : 'admin-submit reject-submit'
                            }
                            disabled={
                              busy ||
                              (
                                decision === 'VERIFIED' &&
                                !canVerify
                              )
                            }
                            onClick={() =>
                              void submitReview(item)
                            }
                          >
                            {busy
                              ? 'Registrando…'
                              : decision === 'VERIFIED'
                                ? 'Aprobar verificación'
                                : 'Registrar rechazo'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          <p className="footnote admin-section-note">
            Cada solicitud requiere una decisión administrativa antes de
            habilitar los productos bancarios.
          </p>
        </section>

        {/* =====================================================
            REVISIÓN CREDITICIA
            ===================================================== */}
        <section
          className="content-card top-gap loan-requests-section admin-work-section credit-review-section"
          aria-labelledby="credit-review-title"
        >
          <div className="section-title admin-section-title">
            <div>
              <div className="eyebrow">
                Crédito de consumo
              </div>

              <h2 id="credit-review-title">Solicitudes de préstamo</h2>
            </div>

            <span
              className="queue-count"
              aria-label={`${pendingLoans.length} solicitudes de préstamo pendientes`}
            >
              {pendingLoans.length}
            </span>
          </div>

          {pendingLoans.length === 0 ? (
            <p className="subtle admin-empty-state" role="status">
              No existen solicitudes de préstamo pendientes.
            </p>
          ) : (
            <div className="loan-review-stack">
              {pendingLoans.map((item) => {
                const isOpen =
                  loanReviewing === item.application_id

                const isApproved =
                  loanDecision === 'APPROVED'

                return (
                  <article
                    className="loan-review-card admin-loan-card"
                    key={item.application_id}
                  >
                    {/* CABECERA DE SOLICITUD */}
                    <div className="loan-review-head">
                      <div className="loan-review-client">
                        <h3>
                          {item.full_name}
                        </h3>

                        <div className="loan-review-overview-grid">
                          <div className="loan-overview-item">
                            <span className="loan-meta-label">
                              Código cliente
                            </span>

                            <span className="loan-meta-value">
                              {item.customer_code}
                            </span>
                          </div>

                          <div className="loan-overview-item">
                            <span className="loan-meta-label">
                              Monto solicitado
                            </span>

                            <strong className="loan-amount-value">
                              {money(
                                item.requested_amount,
                                item.currency,
                              )}
                            </strong>
                          </div>

                          <div className="loan-overview-item">
                            <span className="loan-meta-label">
                              ID solicitud
                            </span>

                            <span className="loan-meta-value mono">
                              {shortId(
                                item.application_id,
                              )}
                            </span>
                          </div>

                          <div className="loan-overview-item">
                            <span className="loan-meta-label">
                              Plazo
                            </span>

                            <span className="loan-meta-value">
                              {item.term_months} meses
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="row-actions admin-review-actions loan-review-actions">
                        <StatusPill
                          value={item.status}
                        />

                        <button
                          type="button"
                          className="secondary-button compact review-action-button"
                          aria-expanded={isOpen}
                          aria-controls={`loan-review-${item.application_id}`}
                          onClick={() =>
                            toggleLoanReview(
                              item.application_id,
                            )
                          }
                        >
                          {isOpen
                            ? 'Cerrar'
                            : 'Revisar'}
                        </button>
                      </div>
                    </div>
                    {/* INFORMACIÓN RESUMIDA */}
                    <div className="loan-review-summary">
                      <div className="loan-summary-item">
                        <span className="field-help">
                          Finalidad
                        </span>

                        <strong>
                          {item.purpose ||
                            'No especificada'}
                        </strong>
                      </div>

                      <div className="loan-summary-item">
                        <span className="field-help">
                          Fecha de solicitud
                        </span>

                        <strong>
                          {dateTime(
                            item.requested_at,
                          )}
                        </strong>
                      </div>

                      <div className="loan-summary-item">
                        <span className="field-help">
                          Evaluación
                        </span>

                        <strong>
                          Revisión humana
                        </strong>
                      </div>

                      <div className="loan-summary-item">
                        <span className="field-help">
                          Estado actual
                        </span>

                        <strong>
                          {uiLabel(item.status)}
                        </strong>
                      </div>

                      <div className="loan-summary-item">
                        <span className="field-help">
                          Cuenta de abono
                        </span>

                        <strong>
                          {item.disbursement_account_last4
                            ? `•••• ${item.disbursement_account_last4} · ${item.currency}`
                            : 'No definida'}
                        </strong>
                      </div>
                    </div>

                    {/* PANEL DE REVISIÓN */}
                    {isOpen && (
                      <div
                        id={`loan-review-${item.application_id}`}
                        className="loan-review-panel admin-review-form"
                        aria-busy={busy}
                      >
                        <div className="decision-block">
                          <span className="field-help">
                            Decisión crediticia
                          </span>

                          <div
                            className="decision-buttons"
                            role="group"
                            aria-label="Decisión crediticia"
                          >
                            <button
                              type="button"
                              aria-pressed={
                                loanDecision ===
                                'APPROVED'
                              }
                              className={
                                loanDecision ===
                                'APPROVED'
                                  ? 'decision-option approve selected'
                                  : 'decision-option approve'
                              }
                              onClick={() =>
                                setLoanDecision(
                                  'APPROVED',
                                )
                              }
                            >
                              Aprobar
                            </button>

                            <button
                              type="button"
                              aria-pressed={
                                loanDecision ===
                                'REJECTED'
                              }
                              className={
                                loanDecision ===
                                'REJECTED'
                                  ? 'decision-option reject selected'
                                  : 'decision-option reject'
                              }
                              onClick={() =>
                                setLoanDecision(
                                  'REJECTED',
                                )
                              }
                            >
                              Rechazar
                            </button>
                          </div>
                        </div>

                        {isApproved && (
                          <label className="field-block admin-rate-field">
                            TEA (%)

                            <input
                              type="number"
                              min="0.01"
                              max="100"
                              step="0.01"
                              value={annualRate}
                              onChange={(e) =>
                                setAnnualRate(
                                  e.target.value,
                                )
                              }
                              required
                            />

                            <span className="field-help">
                              Tasa efectiva anual aplicada al préstamo.
                            </span>
                          </label>
                        )}

                        {!isApproved && (
                          <div className="review-guidance danger" role="note">
                            El rechazo impedirá generar el préstamo para
                            esta solicitud.
                          </div>
                        )}

                        <label className="admin-notes-field">
                          Notas

                          <textarea
                            value={loanNotes}
                            onChange={(e) =>
                              setLoanNotes(
                                e.target.value,
                              )
                            }
                            maxLength={250}
                          />
                        </label>

                        <div className="button-row admin-submit-row">
                          <button
                            type="button"
                            className={
                              isApproved
                                ? 'admin-submit approve-submit'
                                : 'admin-submit reject-submit'
                            }
                            disabled={busy}
                            onClick={() =>
                              void submitLoanReview(
                                item,
                              )
                            }
                          >
                            {busy
                              ? 'Registrando…'
                              : isApproved
                                ? 'Aprobar solicitud'
                                : 'Registrar rechazo'}
                          </button>
                        </div>
                      </div>
                    )}
                  </article>
                )
              })}
            </div>
          )}

          <p className="footnote admin-section-note">
            Cada solicitud crediticia requiere una decisión administrativa
            antes de generar el préstamo.
          </p>
        </section>
      </main>
    </div>
  )
}

function CustomerDashboard({
  dbStatus,
  customer,
  refreshBase,
  onLogout,
}: {
  dbStatus: string
  customer: Customer
  refreshBase: () => Promise<void>
  onLogout: () => void
}) {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loans, setLoans] = useState<LoanApplication[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [movements, setMovements] = useState<Movement[]>([])
  const [cards, setCards] = useState<Card[]>([])
  const [tab, setTab] = useState<CustomerTab>('accounts')
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [documentNumber, setDocumentNumber] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [identityResult, setIdentityResult] =
    useState<IdentityVerificationResponse | null>(null)
  const [accountType, setAccountType] = useState<'SAVINGS' | 'CHECKING'>('SAVINGS')
  const [accountCurrency, setAccountCurrency] = useState<'PEN' | 'USD'>('PEN')
  const [loanAmount, setLoanAmount] = useState('1500')
  const [loanCurrency, setLoanCurrency] = useState<'PEN' | 'USD'>('PEN')
  const [loanTerm, setLoanTerm] = useState<6 | 12 | 18 | 24 | 36 | 48 | 60>(12)
  const [loanPurpose, setLoanPurpose] = useState('Compra de equipo personal')
  const [loanDisbursementAccountId, setLoanDisbursementAccountId] = useState('')
  const [operationType, setOperationType] = useState<'DEPOSIT' | 'WITHDRAWAL' | 'TRANSFER'>('DEPOSIT')
  const [operationAmount, setOperationAmount] = useState('10')

  const selected = useMemo(() => accounts.find((a) => a.id === selectedId) ?? null, [accounts, selectedId])
  const totalPen = useMemo(() => accounts.filter((a) => a.currency === 'PEN').reduce((sum, a) => sum + Number(a.balance), 0), [accounts])
  const totalUsd = useMemo(() => accounts.filter((a) => a.currency === 'USD').reduce((sum, a) => sum + Number(a.balance), 0), [accounts])

  const eligibleLoanDisbursementAccounts = useMemo(
    () =>
      accounts.filter(
        (account) => account.status === 'ACTIVE' && account.currency === loanCurrency,
      ),
    [accounts, loanCurrency],
  )

  const effectiveLoanDisbursementAccountId = useMemo(() => {
    if (
      eligibleLoanDisbursementAccounts.some(
        (account) => account.id === loanDisbursementAccountId,
      )
    ) {
      return loanDisbursementAccountId
    }

    return eligibleLoanDisbursementAccounts[0]?.id ?? ''
  }, [eligibleLoanDisbursementAccounts, loanDisbursementAccountId])

  useEffect(() => {
    let cancelled = false
    async function loadProducts() {
      if (customer.onboarding_status !== 'VERIFIED') return
      try {
        const [a, l] = await Promise.all([getCustomerAccounts(customer.id), getLoanApplications(customer.id)])
        if (!cancelled) {
          setAccounts(a)
          setLoans(l)
          if (a[0]) setSelectedId((current) => current || a[0].id)
        }
      } catch (err) {
        if (!cancelled) setError(readableError(err))
      }
    }
    void loadProducts()
    return () => { cancelled = true }
  }, [customer.id, customer.onboarding_status])

  useEffect(() => {
    let cancelled = false
    async function loadDetail() {
      if (!selectedId) { setMovements([]); setCards([]); return }
      setLoadingDetail(true)
      try {
        const [m, c] = await Promise.all([getMovements(selectedId), getCards(selectedId)])
        if (!cancelled) { setMovements(m); setCards(c) }
      } catch (err) {
        if (!cancelled) setError(readableError(err))
      } finally {
        if (!cancelled) setLoadingDetail(false)
      }
    }
    void loadDetail()
    return () => { cancelled = true }
  }, [selectedId])

  async function reloadCustomerData() {
    const [a, l] = await Promise.all([getCustomerAccounts(customer.id), getLoanApplications(customer.id)])
    setAccounts(a); setLoans(l)
    if (!selectedId && a[0]) setSelectedId(a[0].id)
    if (selectedId) {
      const [m, c] = await Promise.all([getMovements(selectedId), getCards(selectedId)])
      setMovements(m); setCards(c)
    }
    await refreshBase()
  }

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(''); setMessage('')
    try { await action(); setMessage(success); await reloadCustomerData() }
    catch (err) { setError(readableError(err)) }
    finally { setBusy(false) }
  }


async function handleIdentityVerification(event: FormEvent) {
  event.preventDefault()

  setBusy(true)
  setError('')
  setMessage('')
  setIdentityResult(null)

  try {
    const result = await verifyIdentity({
      document_number: documentNumber.trim(),
      birth_date: birthDate,
    })

    setIdentityResult(result)

    if (result.result === 'MATCH') {
      setMessage(
        'Identidad validada correctamente. La evidencia fue enviada para revisión administrativa.',
      )
    } else {
      setError(
        `La verificación de identidad obtuvo el resultado: ${uiLabel(result.result)}.`,
      )
    }
  } catch (err) {
    setError(readableError(err))
  } finally {
    setBusy(false)
  }
}

  async function handleCreateAccount(event: FormEvent) {
    event.preventDefault()
    await run(() => createAccount({ customer_id: customer.id, account_type: accountType, currency: accountCurrency }), 'Cuenta creada correctamente.')
  }

  async function handleLoan(event: FormEvent) {
    event.preventDefault()
    const amount = Number(loanAmount)
    if (!Number.isFinite(amount)) { setError('Monto inválido.'); return }
    if (!effectiveLoanDisbursementAccountId) {
      setError('Selecciona una cuenta activa para recibir el desembolso.')
      return
    }
    await run(
      () => submitLoanApplication({
        customer_id: customer.id,
        requested_amount: amount,
        currency: loanCurrency,
        term_months: loanTerm,
        purpose: loanPurpose.trim(),
        disbursement_account_id: effectiveLoanDisbursementAccountId,
      }),
      'Solicitud de préstamo registrada para revisión humana.',
    )
  }

  async function handleOperation(
    event: FormEvent,
    transferDraft?: TransferDraft,
  ) {
    event.preventDefault()

    if (!selected) {
      setError('Selecciona una cuenta.')
      return
    }

    const amount = Number(operationAmount)

    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Monto inválido.')
      return
    }

    const currency = selected.currency as 'PEN' | 'USD'

    if (operationType === 'DEPOSIT') {
      const key = newIdempotencyKey('WEB-DEPOSIT')
      await run(
        () =>
          deposit({
            account_id: selected.id,
            amount,
            currency,
            idempotency_key: key,
          }),
        'Depósito completado.',
      )
      return
    }

    if (operationType === 'WITHDRAWAL') {
      const key = newIdempotencyKey('WEB-WITHDRAWAL')
      await run(
        () =>
          withdraw({
            account_id: selected.id,
            amount,
            currency,
            idempotency_key: key,
          }),
        'Retiro completado.',
      )
      return
    }

    if (!transferDraft) {
      setError('Selecciona el tipo de transferencia.')
      return
    }

    if (transferDraft.scope === 'OWN_ACCOUNTS') {
      if (!transferDraft.ownTarget) {
        setError('Selecciona una cuenta destino.')
        return
      }

      const key = newIdempotencyKey('WEB-TRANSFER-OWN')

      await run(
        () =>
          transfer({
            source_account_id: selected.id,
            target_account_id: transferDraft.ownTarget,
            amount,
            currency,
            idempotency_key: key,
          }),
        'Transferencia entre tus cuentas completada.',
      )
      return
    }

    if (transferDraft.scope === 'BANCOCLOUD_THIRD_PARTY') {
      const accountNumber =
        transferDraft.thirdPartyAccountNumber
          .trim()
          .toUpperCase()

      if (!accountNumber) {
        setError('Ingresa la cuenta BancoCloud del destinatario.')
        return
      }

      const key = newIdempotencyKey('WEB-TRANSFER-THIRD')

      await run(
        () =>
          transferToBancoCloudThirdParty({
            source_account_id: selected.id,
            target_account_number: accountNumber,
            amount,
            currency,
            idempotency_key: key,
          }),
        'Transferencia a tercero BancoCloud completada.',
      )
      return
    }

    const cci = transferDraft.interbankCci.replace(/\s+/g, '')

    if (!/^\d{20}$/.test(cci)) {
      setError('El CCI debe contener exactamente 20 dígitos.')
      return
    }

    const key = newIdempotencyKey('WEB-TRANSFER-INTERBANK')

    await run(
      () =>
        transferInterbank({
          source_account_id: selected.id,
          cci,
          destination_bank: transferDraft.interbankBank,
          amount,
          currency,
          idempotency_key: key,
        }),
      'Transferencia interbancaria registrada correctamente.',
    )
  }

  return (
    <div className="app-shell">
      <Topbar onLogout={onLogout} />
      <main className="dashboard wide-dashboard">
        <CustomerOverview
          dbStatus={dbStatus}
          customer={customer}
          accountCount={accounts.length}
          totalPen={totalPen}
          totalUsd={totalUsd}
        />

        {message && (
          <div
            className={`message success block-gap ${tab === 'operations' ? 'operation-feedback' : ''}`}
            role={tab === 'operations' ? 'status' : undefined}
          >
            {message}
          </div>
        )}
        {error && (
          <div
            className={`message error block-gap ${tab === 'operations' ? 'operation-feedback' : ''}`}
            role={tab === 'operations' ? 'alert' : undefined}
          >
            {error}
          </div>
        )}

{customer.onboarding_status !== 'VERIFIED' ? (
  <section className="content-card identity-verification-card">
    <div className="section-title">
      <div>
        <div className="eyebrow">Validación de identidad</div>
        <h2>RENIEC Simulator</h2>
      </div>

      <StatusPill value={customer.onboarding_status} />
    </div>

    <p className="subtle">
      Completa la validación de identidad para habilitar tus productos bancarios.
    </p>

    {customer.onboarding_status === 'PENDING' && (
      <form
        className="identity-form"
        onSubmit={handleIdentityVerification}
      >
        <div className="identity-form-row">
          <label className="field-block">
            DNI
            <input
              value={documentNumber}
              onChange={(e) => setDocumentNumber(e.target.value)}
              inputMode="numeric"
              pattern="[0-9]{8}"
              minLength={8}
              maxLength={8}
              placeholder="70000001"
              required
            />
            <span className="field-help">
              Ingresa tu documento de 8 dígitos.
            </span>
          </label>

          <label className="field-block">
            Fecha de nacimiento
            <input
              type="date"
              value={birthDate}
              onChange={(e) => setBirthDate(e.target.value)}
              required
            />
          </label>
        </div>

        <div className="button-row align-right">
          <button
            className="primary-button"
            type="submit"
            disabled={busy}
          >
            {busy ? 'Verificando...' : 'Verificar identidad'}
          </button>
        </div>
      </form>
    )}

    {identityResult && (
      <div className="identity-result-grid">
        <div className="result-item">
          <span className="field-help">Resultado RENIEC</span>
          <StatusPill value={identityResult.result} />
        </div>

        <div className="result-item">
          <span className="field-help">Estado del documento</span>
          <StatusPill
            value={identityResult.document_status ?? 'NOT_FOUND'}
          />
        </div>

        <div className="result-item">
          <span className="field-help">Nombre</span>
          <StatusPill
            value={
              identityResult.matched_name
                ? 'COINCIDE'
                : 'NO COINCIDE'
            }
          />
        </div>

        <div className="result-item">
          <span className="field-help">Fecha de nacimiento</span>
          <StatusPill
            value={
              identityResult.matched_birth_date
                ? 'COINCIDE'
                : 'NO COINCIDE'
            }
          />
        </div>

        <div className="result-item full-width">
          <span className="field-help">
            Referencia de evidencia
          </span>
          <div className="mono">
            {identityResult.evidence_ref}
          </div>
        </div>

        <div className="result-item full-width">
          <span className="field-help">Fuente</span>
          <div>RENIEC Simulator</div>
        </div>
      </div>
    )}

    <p className="footnote">
      {identityResult
        ? 'Tu validación fue registrada correctamente. Te informaremos cuando el proceso haya finalizado.'
        : 'Verifica tu DNI y tu fecha de nacimiento para continuar con tu proceso.'}
    </p>
  </section>
) : (
  <>
    <CustomerTabbar tab={tab} onTabChange={setTab} />

    <CustomerWorkspace
      accounts={accounts}
      selectedId={selectedId}
      onSelectAccount={setSelectedId}
    >
        {tab === 'accounts' && (
          <AccountsPane
            accounts={accounts}
            onSubmit={handleCreateAccount}
            accountType={accountType}
            setAccountType={setAccountType}
            currency={accountCurrency}
            setCurrency={setAccountCurrency}
            busy={busy}
          />
        )}

        {tab === 'movements' && (
          <MovementsPane
            selected={selected}
            movements={movements}
            loading={loadingDetail}
          />
        )}

        {tab === 'cards' && (
          <CardsPane
            selected={selected}
            cards={cards}
            busy={busy}
            issue={() =>
              selected &&
              run(
                () => issueCard(selected.id),
                'Tarjeta emitida.',
              )
            }
          />
        )}

        {tab === 'loans' && (
          <LoansPane
            customerId={customer.id}
            accounts={accounts}
            disbursementAccountId={effectiveLoanDisbursementAccountId}
            setDisbursementAccountId={setLoanDisbursementAccountId}
            loans={loans}
            submit={handleLoan}
            amount={loanAmount}
            setAmount={setLoanAmount}
            currency={loanCurrency}
            setCurrency={setLoanCurrency}
            term={loanTerm}
            setTerm={setLoanTerm}
            purpose={loanPurpose}
            setPurpose={setLoanPurpose}
            busy={busy}
          />
        )}

        {tab === 'operations' && (
          <OperationsPane
            selected={selected}
            accounts={accounts}
            type={operationType}
            setType={setOperationType}
            amount={operationAmount}
            setAmount={setOperationAmount}
            submit={handleOperation}
            busy={busy}
          />
        )}
    </CustomerWorkspace>
  </>
)}
        <p className="footnote center-note">TRAZA</p>
      </main>
    </div>
  )
}

function LoansPane({
  customerId,
  accounts,
  disbursementAccountId,
  setDisbursementAccountId,
  loans,
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
  customerId: string
  accounts: Account[]
  disbursementAccountId: string
  setDisbursementAccountId: (value: string) => void
  loans: LoanApplication[]
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
  const [approvedLoans, setApprovedLoans] = useState<LoanSummary[]>([])
  const [scheduleLoanId, setScheduleLoanId] = useState<string | null>(null)
  const [installments, setInstallments] = useState<LoanInstallmentDetail[]>([])
  const [loadingApproved, setLoadingApproved] = useState(false)
  const [loanError, setLoanError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadApprovedLoans() {
      setLoadingApproved(true)
      setLoanError('')
      try {
        const data = await getCustomerLoans(customerId)
        if (!cancelled) setApprovedLoans(data)
      } catch (err) {
        if (!cancelled) setLoanError(readableError(err))
      } finally {
        if (!cancelled) setLoadingApproved(false)
      }
    }

    void loadApprovedLoans()
    return () => {
      cancelled = true
    }
  }, [customerId, loans])

  const eligibleDisbursementAccounts = accounts.filter(
    (account) => account.status === 'ACTIVE' && account.currency === currency,
  )

  async function toggleSchedule(loanId: string) {
    if (scheduleLoanId === loanId) {
      setScheduleLoanId(null)
      setInstallments([])
      return
    }

    setLoanError('')
    try {
      const data = await getLoanInstallments(loanId)
      setInstallments(data)
      setScheduleLoanId(loanId)
    } catch (err) {
      setLoanError(readableError(err))
    }
  }

  return (
    <>
      <LoanApplicationForm
        eligibleDisbursementAccounts={eligibleDisbursementAccounts}
        disbursementAccountId={disbursementAccountId}
        setDisbursementAccountId={setDisbursementAccountId}
        submit={submit}
        amount={amount}
        setAmount={setAmount}
        currency={currency}
        setCurrency={setCurrency}
        term={term}
        setTerm={setTerm}
        purpose={purpose}
        setPurpose={setPurpose}
        busy={busy}
      />

      <LoanApplicationsTable loans={loans} />

      <div className="section-title loan-section-gap">
        <div className="loan-financing-heading">
          <div className="eyebrow">Financiamiento</div>
          <h2>Mis préstamos</h2>
        </div>
      </div>

      <ApprovedLoansList
        approvedLoans={approvedLoans}
        loadingApproved={loadingApproved}
        loanError={loanError}
        scheduleLoanId={scheduleLoanId}
        installments={installments}
        toggleSchedule={toggleSchedule}
      />

      <p className="footnote">Las solicitudes son evaluadas antes de su aprobación.</p>
    </>
  )
}

const INTERBANK_BANK_OPTIONS: Array<{
  code: InterbankBankCode
  label: string
}> = [
  { code: 'BCP', label: 'BCP' },
  { code: 'INTERBANK', label: 'Interbank' },
  { code: 'BBVA', label: 'BBVA' },
  { code: 'SCOTIABANK', label: 'Scotiabank' },
  { code: 'BANBIF', label: 'BanBif' },
  { code: 'BANCO_NACION', label: 'Banco de la Nación' },
]

function OperationsPane({
  selected,
  accounts,
  type,
  setType,
  amount,
  setAmount,
  submit,
  busy,
}: {
  selected: Account | null
  accounts: Account[]
  type: 'DEPOSIT' | 'WITHDRAWAL' | 'TRANSFER'
  setType: (v: 'DEPOSIT' | 'WITHDRAWAL' | 'TRANSFER') => void
  amount: string
  setAmount: (v: string) => void
  submit: (e: FormEvent, transferDraft?: TransferDraft) => void
  busy: boolean
}) {
  const [transferScope, setTransferScope] =
    useState<TransferScope>('OWN_ACCOUNTS')
  const [ownTarget, setOwnTarget] = useState('')
  const [thirdPartyAccountNumber, setThirdPartyAccountNumber] =
    useState('')
  const [thirdPartyPreview, setThirdPartyPreview] =
    useState<ThirdPartyBeneficiary | null>(null)
  const [beneficiarySourceId, setBeneficiarySourceId] =
    useState('')
  const [beneficiaryError, setBeneficiaryError] = useState('')
  const [resolvingBeneficiary, setResolvingBeneficiary] =
    useState(false)
  const [interbankCci, setInterbankCci] = useState('')
  const [interbankBank, setInterbankBank] =
    useState<InterbankBankCode>('BCP')

  const eligibleTargets = selected
    ? accounts.filter(
        (account) =>
          account.id !== selected.id &&
          account.currency === selected.currency &&
          account.status === 'ACTIVE',
      )
    : []

  async function resolveBeneficiary() {
    if (!selected) return

    const accountNumber =
      thirdPartyAccountNumber.trim().toUpperCase()

    if (!accountNumber) {
      setBeneficiaryError(
        'Ingresa la cuenta BancoCloud del destinatario.',
      )
      return
    }

    setResolvingBeneficiary(true)
    setBeneficiaryError('')
    setThirdPartyPreview(null)

    try {
      const result = await resolveBancoCloudBeneficiary({
        source_account_id: selected.id,
        target_account_number: accountNumber,
      })

      setThirdPartyPreview(result)
      setBeneficiarySourceId(selected.id)
    } catch (error) {
      setBeneficiaryError(readableError(error))
    } finally {
      setResolvingBeneficiary(false)
    }
  }

  const transferDraft: TransferDraft = {
    scope: transferScope,
    ownTarget,
    thirdPartyAccountNumber:
      thirdPartyAccountNumber.trim().toUpperCase(),
    interbankCci: interbankCci.replace(/\s+/g, ''),
    interbankBank,
  }

  return (
    <section className="customer-product-pane operations-pane" aria-labelledby="operations-title">
      <div className="section-title customer-section-header operations-header">
        <div>
          <div className="eyebrow">Motor transaccional</div>
          <h2 id="operations-title">Operación</h2>
        </div>
      </div>

      {!selected ? (
        <p className="subtle customer-empty-state">Selecciona una cuenta.</p>
      ) : (
        <>
          <div className="selected-account-banner operation-source-card" aria-label="Cuenta origen seleccionada">
            <div className="operation-source-details">
              <span className="operation-meta-label">Cuenta origen</span>
              <strong>
                {uiLabel(selected.account_type)} · {selected.currency}
              </strong>
              <span className="mono operation-source-number">
                …{selected.account_number.slice(-8)}
              </span>
            </div>

            <div className="operation-source-balance">
              <span className="operation-meta-label">Saldo disponible</span>
              <strong>
                {money(selected.balance, selected.currency)}
              </strong>
            </div>
          </div>

          <form
            className={
              type === 'TRANSFER'
                ? 'operation-form customer-operation-form transfer-operation-form'
                : 'operation-form customer-operation-form'
            }
            aria-busy={busy}
            onSubmit={(event) =>
              submit(
                event,
                type === 'TRANSFER'
                  ? transferDraft
                  : undefined,
              )
            }
          >
            <label className="operation-type-field">
              <span className="field-label">Operación</span>

              <select
                value={type}
                onChange={(e) => {
                  setType(
                    e.target.value as
                      | 'DEPOSIT'
                      | 'WITHDRAWAL'
                      | 'TRANSFER',
                  )

                  setOwnTarget('')
                  setThirdPartyPreview(null)
                  setBeneficiarySourceId('')
                  setBeneficiaryError('')
                }}
              >
                <option value="DEPOSIT">Depósito</option>
                <option value="WITHDRAWAL">Retiro</option>
                <option value="TRANSFER">Transferencia</option>
              </select>
            </label>

            <label className="operation-amount-field">
              <span className="field-label">Monto</span>

              <div className="operation-amount-input">
                <input
                  type="number"
                  min="0.01"
                  max="10000"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                />
                <span aria-hidden="true">{selected.currency}</span>
              </div>
            </label>

            {type === 'TRANSFER' && (
              <>
                <label className="full-width transfer-scope-field">
                  <span className="field-label">Tipo de transferencia</span>

                  <select
                    value={transferScope}
                    onChange={(e) => {
                      setTransferScope(
                        e.target.value as TransferScope,
                      )
                      setOwnTarget('')
                      setThirdPartyPreview(null)
                      setBeneficiarySourceId('')
                      setBeneficiaryError('')
                    }}
                  >
                    <option value="OWN_ACCOUNTS">
                      Entre mis cuentas
                    </option>
                    <option value="BANCOCLOUD_THIRD_PARTY">
                      A terceros TRAZA
                    </option>
                    <option value="INTERBANK">
                      A otros bancos
                    </option>
                  </select>
                </label>

                {transferScope === 'OWN_ACCOUNTS' && (
                  <label className="full-width transfer-own-target-field">
                    <span className="field-label">Cuenta destino</span>

                    <select
                      value={ownTarget}
                      onChange={(e) =>
                        setOwnTarget(e.target.value)
                      }
                      required
                    >
                      <option value="">
                        Selecciona una cuenta destino
                      </option>

                      {eligibleTargets.map((account) => (
                        <option
                          key={account.id}
                          value={account.id}
                        >
                          {uiLabel(account.account_type)}
                          {' · '}
                          {account.currency}
                          {' · '}
                          ••••{account.account_number.slice(-6)}
                          {' · '}
                          {money(
                            account.balance,
                            account.currency,
                          )}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {transferScope ===
                  'BANCOCLOUD_THIRD_PARTY' && (
                  <div className="full-width transfer-destination-panel transfer-mode-panel third-party-transfer-panel">
                    <div className="transfer-panel-heading">
                      <span>Destinatario TRAZA</span>
                      <strong>Valida la cuenta antes de transferir</strong>
                    </div>

                    <label className="transfer-destination-field">
                      <span className="field-label">Cuenta TRAZA destino</span>

                      <div className="transfer-resolve-row">
                        <input
                          value={thirdPartyAccountNumber}
                          onChange={(e) => {
                            setThirdPartyAccountNumber(
                              e.target.value,
                            )
                            setThirdPartyPreview(null)
                            setBeneficiarySourceId('')
                            setBeneficiaryError('')
                          }}
                          minLength={8}
                          maxLength={30}
                          autoComplete="off"
                          placeholder="BC..."
                          required
                        />

                        <button
                          type="button"
                          className="secondary-button"
                          disabled={
                            resolvingBeneficiary ||
                            !thirdPartyAccountNumber.trim()
                          }
                          onClick={() =>
                            void resolveBeneficiary()
                          }
                        >
                          {resolvingBeneficiary
                            ? 'Validando…'
                            : 'Validar cuenta'}
                        </button>
                      </div>
                    </label>

                    {thirdPartyPreview &&
                      beneficiarySourceId === selected.id && (
                      <div
                        className="review-guidance success transfer-beneficiary-preview"
                        role="status"
                        aria-live="polite"
                      >
                        <strong>
                          Destinatario validado
                        </strong>
                        <span>
                          {thirdPartyPreview.holder_display}
                          {' · '}
                          {uiLabel(
                            thirdPartyPreview.account_type,
                          )}
                          {' · '}
                          {thirdPartyPreview.currency}
                          {' · '}
                          ••••{thirdPartyPreview.account_last4}
                        </span>
                      </div>
                    )}

                    {beneficiaryError && (
                      <div
                        className="review-guidance danger transfer-beneficiary-preview"
                        role="alert"
                      >
                        {beneficiaryError}
                      </div>
                    )}
                  </div>
                )}

                {transferScope === 'INTERBANK' && (
                  <div className="full-width transfer-destination-panel transfer-mode-panel interbank-transfer-panel">
                    <div className="transfer-panel-heading">
                      <span>Destino bancario</span>
                      <strong>Transferencia a otros bancos</strong>
                    </div>

                    <div className="transfer-interbank-grid">
                      <label>
                        <span className="field-label">Banco destino</span>

                        <select
                          value={interbankBank}
                          onChange={(e) =>
                            setInterbankBank(
                              e.target
                                .value as InterbankBankCode,
                            )
                          }
                        >
                          {INTERBANK_BANK_OPTIONS.map(
                            (bank) => (
                              <option
                                key={bank.code}
                                value={bank.code}
                              >
                                {bank.label}
                              </option>
                            ),
                          )}
                        </select>
                      </label>

                      <label>
                        <span className="field-label">CCI / cuenta interbancaria</span>

                        <input
                          value={interbankCci}
                          onChange={(e) =>
                            setInterbankCci(
                              e.target.value.replace(
                                /\D/g,
                                '',
                              ),
                            )
                          }
                          inputMode="numeric"
                          pattern="[0-9]{20}"
                          minLength={20}
                          maxLength={20}
                          placeholder="20 dígitos"
                          required
                        />
                      </label>
                    </div>

                    <div className="review-guidance warning transfer-beneficiary-preview" role="note">
                      Verifica que el banco destino y el CCI correspondan al beneficiario antes de continuar.
                    </div>
                  </div>
                )}

                <div className="button-row full-width transfer-submit-row">
                  <button
                    className="primary-button operation-submit-button"
                    disabled={
                      busy ||
                      (transferScope === 'OWN_ACCOUNTS' &&
                        (!ownTarget ||
                          !eligibleTargets.some(
                            (account) =>
                              account.id === ownTarget,
                          ))) ||
                      (transferScope ===
                        'BANCOCLOUD_THIRD_PARTY' &&
                        (!thirdPartyPreview ||
                          beneficiarySourceId !== selected.id))
                    }
                  >
                    Ejecutar transferencia
                  </button>
                </div>
              </>
            )}

            {type !== 'TRANSFER' && (
              <button
                className="primary-button operation-submit-button"
                disabled={busy}
              >
                Ejecutar operación
              </button>
            )}
          </form>

          {type === 'TRANSFER' &&
            transferScope === 'OWN_ACCOUNTS' &&
            eligibleTargets.length === 0 && (
              <p className="footnote operation-availability-note" role="status">
                No existe otra cuenta ACTIVE en la misma moneda
                disponible como destino.
              </p>
            )}
        </>
      )}

      <p className="footnote operations-security-note">
        Tus operaciones se procesan de forma segura y quedan registradas.
      </p>
    </section>
  )
}

type DashboardSnapshot = {
  dbStatus: string
  customer: Customer | null
  pending: PendingOnboarding[]
  pendingLoans: PendingLoanApplication[]
}

async function fetchDashboardSnapshot(user: CurrentUser): Promise<DashboardSnapshot> {
  const health = await getDatabaseHealth()

  if (user.role === 'CUSTOMER' && user.customer_id) {
    const profile = await getCustomer(user.customer_id)
    return {
      dbStatus: health.connection,
      customer: profile,
      pending: [],
      pendingLoans: [],
    }
  }

  if (user.role === 'ADMIN') {
    const [pending, pendingLoans] = await Promise.all([
      getPendingOnboarding(),
      getPendingLoanApplications(),
    ])

    return {
      dbStatus: health.connection,
      customer: null,
      pending,
      pendingLoans,
    }
  }

  return {
    dbStatus: health.connection,
    customer: null,
    pending: [],
    pendingLoans: [],
  }
}

function Dashboard({ user, onLogout }: { user: CurrentUser; onLogout: () => void }) {
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [pending, setPending] = useState<PendingOnboarding[]>([])
  const [pendingLoans, setPendingLoans] = useState<PendingLoanApplication[]>([])
  const [dbStatus, setDbStatus] = useState('Comprobando…')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  function applySnapshot(snapshot: DashboardSnapshot) {
    setDbStatus(snapshot.dbStatus)
    setCustomer(snapshot.customer)
    setPending(snapshot.pending)
      setPendingLoans(snapshot.pendingLoans)
    setError('')
    setLoading(false)
  }

  async function refreshDashboard() {
    try {
      const snapshot = await fetchDashboardSnapshot(user)
      applySnapshot(snapshot)
    } catch (err) {
      setError(readableError(err))
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false

    fetchDashboardSnapshot(user)
      .then((snapshot) => {
        if (!cancelled) {
          setDbStatus(snapshot.dbStatus)
          setCustomer(snapshot.customer)
          setPending(snapshot.pending)
      setPendingLoans(snapshot.pendingLoans)
          setError('')
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(readableError(err))
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [user])

  if (loading && user.role === 'CUSTOMER') return <div className="loading-screen">Cargando TRAZA…</div>
  if (error && !customer && user.role === 'CUSTOMER') return <div className="loading-screen">{error}</div>

  if (user.role === 'ADMIN') return <AdminDashboard user={user} dbStatus={dbStatus} pending={pending} pendingLoans={pendingLoans} refresh={refreshDashboard} onLogout={onLogout} />
  if (customer) return <CustomerDashboard dbStatus={dbStatus} customer={customer} refreshBase={refreshDashboard} onLogout={onLogout} />
  return <div className="loading-screen">No se pudo cargar el perfil del cliente.</div>
}

export default function App() {
  const [view, setView] = useState<View>('login')
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [restoring, setRestoring] = useState(true)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let cancelled = false
    async function restore() {
      if (!hasSession()) { setRestoring(false); return }
      try { const current = await getCurrentUser(); if (!cancelled) setUser(current) }
      catch { clearSession() }
      finally { if (!cancelled) setRestoring(false) }
    }
    void restore(); return () => { cancelled = true }
  }, [])

  function logout() {
    clearSession(); setUser(null); setView('login'); setNotice('Sesión cerrada correctamente.')
  }

  if (restoring) return <div className="loading-screen auth-loading-screen">Inicializando TRAZA…</div>
  if (user) return <Dashboard user={user} onLogout={logout} />

  return (
    <div className="auth-page">
      <div className="auth-background" aria-hidden="true" />

      <main className="auth-layout">
        <section className="auth-copy" aria-labelledby="public-heading">
          <div className="eyebrow">Plataforma bancaria integrada</div>
          <h2 id="public-heading">Operaciones seguras y trazables de extremo a extremo.</h2>
          <p>Conecta operación, auditoría, calidad de datos y supervisión en una sola plataforma.</p>
          <ul className="security-points" aria-label="Ventajas de TRAZA">
            <li>Trazabilidad operativa</li>
            <li>Datos confiables</li>
            <li>IA supervisada</li>
          </ul>
        </section>

        <div className="auth-panel">
          {notice && (
            <div className="message success auth-notice" role="status">
              {notice}
            </div>
          )}

          {view === 'login' ? (
            <LoginPanel
              onAuthenticated={(current) => { setNotice(''); setUser(current) }}
              onRegister={() => { setNotice(''); setView('register') }}
            />
          ) : (
            <RegisterPanel
              onBack={() => setView('login')}
              onRegistered={(registeredEmail) => {
                setView('login')
                setNotice(`Cliente ${registeredEmail} registrado. Su verificación permanece Pendiente hasta revisión humana.`)
              }}
            />
          )}
        </div>
      </main>

      <footer className="public-footer">TRAZA · Banca digital</footer>
    </div>
  )
}

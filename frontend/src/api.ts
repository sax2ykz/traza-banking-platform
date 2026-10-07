import type { LoanInstallmentDetail, LoanSummary } from './types'
import type { LoanAdminReviewPayload, LoanAdminReviewResponse, PendingLoanApplication } from './types'
import type {
  Account,
  AuthToken,
  Card,
  CurrentUser,
  Customer,
  DatabaseHealth,
  LoanApplication,
  Movement,
  OperationResult,
  PendingOnboarding,
  IdentityVerificationResponse,
  RegisterResponse,
  ReviewPayload,
  ReviewResponse,
} from './types'
import type { InterbankBankCode, ThirdPartyBeneficiary } from './types'

const TOKEN_KEY = 'bancocloud_access_token'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? ''
).replace(/\/$/, '')

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function getErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'object' && item !== null && 'msg' in item) {
            return String((item as { msg?: unknown }).msg)
          }
          return String(item)
        })
        .join('; ')
    }
  }
  return fallback
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  authenticated = false,
): Promise<T> {
  const headers = new Headers(init.headers)

  if (authenticated) {
    const token = sessionStorage.getItem(TOKEN_KEY)
    if (!token) throw new ApiError('Sesión no disponible.', 401)
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(apiUrl(path), { ...init, headers })
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload: unknown = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(payload, `Solicitud rechazada (HTTP ${response.status}).`),
      response.status,
    )
  }

  return payload as T
}

function jsonRequest<T>(path: string, method: 'POST' | 'PUT' | 'PATCH', body: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, true)
}

export function hasSession(): boolean {
  return Boolean(sessionStorage.getItem(TOKEN_KEY))
}

export function clearSession(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const form = new URLSearchParams()
  form.set('username', email.trim().toLowerCase())
  form.set('password', password)

  const token = await request<AuthToken>('/api/v1/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  })

  sessionStorage.setItem(TOKEN_KEY, token.access_token)

  try {
    return await getCurrentUser()
  } catch (error) {
    clearSession()
    throw error
  }
}

export async function registerCustomer(input: {
  full_name: string
  email: string
  region: string
  password: string
}): Promise<RegisterResponse> {
  return request<RegisterResponse>('/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>('/api/v1/auth/me', {}, true)
}

export function getCustomer(customerId: string): Promise<Customer> {
  return request<Customer>(`/api/v1/customers/${customerId}`, {}, true)
}

export function getCustomerAccounts(customerId: string): Promise<Account[]> {
  return request<Account[]>(`/api/v1/customers/${customerId}/accounts`, {}, true)
}

export function createAccount(input: {
  customer_id: string
  account_type: 'SAVINGS' | 'CHECKING'
  currency: 'PEN' | 'USD'
}): Promise<Account> {
  return jsonRequest<Account>('/api/v1/accounts', 'POST', input)
}

export function getMovements(accountId: string): Promise<Movement[]> {
  return request<Movement[]>(`/api/v1/accounts/${accountId}/movements?limit=30`, {}, true)
}

export function getCards(accountId: string): Promise<Card[]> {
  return request<Card[]>(`/api/v1/accounts/${accountId}/cards`, {}, true)
}

export function issueCard(accountId: string): Promise<Card> {
  return jsonRequest<Card>('/api/v1/cards', 'POST', { account_id: accountId })
}

export function getLoanApplications(customerId: string): Promise<LoanApplication[]> {
  return request<LoanApplication[]>(`/api/v1/customers/${customerId}/loan-applications`, {}, true)
}

export function submitLoanApplication(input: {
  customer_id: string
  requested_amount: number
  currency: 'PEN' | 'USD'
  term_months: 6 | 12 | 18 | 24 | 36 | 48 | 60
  purpose: string
  disbursement_account_id: string
}): Promise<LoanApplication> {
  return jsonRequest<LoanApplication>('/api/v1/loan-applications', 'POST', input)
}

export function deposit(input: {
  account_id: string
  amount: number
  currency: 'PEN' | 'USD'
  idempotency_key: string
}): Promise<OperationResult> {
  return jsonRequest<OperationResult>('/api/v1/operations/deposit', 'POST', input)
}

export function withdraw(input: {
  account_id: string
  amount: number
  currency: 'PEN' | 'USD'
  idempotency_key: string
}): Promise<OperationResult> {
  return jsonRequest<OperationResult>('/api/v1/operations/withdraw', 'POST', input)
}

export function transfer(input: {
  source_account_id: string
  target_account_id: string
  amount: number
  currency: 'PEN' | 'USD'
  idempotency_key: string
}): Promise<OperationResult> {
  return jsonRequest<OperationResult>('/api/v1/operations/transfer', 'POST', input)
}


export function resolveBancoCloudBeneficiary(input: {
  source_account_id: string
  target_account_number: string
}): Promise<ThirdPartyBeneficiary> {
  return jsonRequest<ThirdPartyBeneficiary>(
    '/api/v1/operations/transfer/beneficiary/resolve',
    'POST',
    input,
  )
}

export function transferToBancoCloudThirdParty(input: {
  source_account_id: string
  target_account_number: string
  amount: number
  currency: 'PEN' | 'USD'
  idempotency_key: string
}): Promise<OperationResult> {
  return jsonRequest<OperationResult>(
    '/api/v1/operations/transfer/third-party',
    'POST',
    input,
  )
}

export function transferInterbank(input: {
  source_account_id: string
  cci: string
  destination_bank: InterbankBankCode
  amount: number
  currency: 'PEN' | 'USD'
  idempotency_key: string
}): Promise<OperationResult> {
  return jsonRequest<OperationResult>(
    '/api/v1/operations/transfer/interbank',
    'POST',
    input,
  )
}

export function getPendingOnboarding(): Promise<PendingOnboarding[]> {
  return request<PendingOnboarding[]>('/api/v1/admin/onboarding/pending', {}, true)
}

export function verifyIdentity(input: {
  document_number: string
  birth_date: string
}): Promise<IdentityVerificationResponse> {
  return jsonRequest<IdentityVerificationResponse>(
    '/api/v1/onboarding/identity/verify',
    'POST',
    input,
  )
}

export function reviewOnboarding(customerId: string, payload: ReviewPayload): Promise<ReviewResponse> {
  return jsonRequest<ReviewResponse>(`/api/v1/admin/onboarding/${customerId}/review`, 'POST', payload)
}

export function getDatabaseHealth(): Promise<DatabaseHealth> {
  return request<DatabaseHealth>('/health/db')
}


export function getPendingLoanApplications(): Promise<PendingLoanApplication[]> {
  return request<PendingLoanApplication[]>('/api/v1/admin/loans/pending', {}, true)
}

export function reviewLoanApplication(
  applicationId: string,
  payload: LoanAdminReviewPayload,
): Promise<LoanAdminReviewResponse> {
  return jsonRequest<LoanAdminReviewResponse>(
    `/api/v1/admin/loans/${applicationId}/review`,
    'POST',
    payload,
  )
}

export function getCustomerLoans(customerId: string): Promise<LoanSummary[]> {
  return request<LoanSummary[]>(`/api/v1/customers/${customerId}/loans`, {}, true)
}

export function getLoanInstallments(loanId: string): Promise<LoanInstallmentDetail[]> {
  return request<LoanInstallmentDetail[]>(`/api/v1/loans/${loanId}/installments`, {}, true)
}

// =====================================================
// Operations Control Tower
// =====================================================

import type {
  ControlTowerActionResult,
  ControlTowerDataOps,
  ControlTowerDecision,
  ControlTowerOperation,
  ControlTowerOperationTrace,
  ControlTowerOverview,
} from './types'

export function getControlTowerOverview(): Promise<ControlTowerOverview> {
  return request<ControlTowerOverview>(
    '/api/v1/admin/control-tower/overview',
    {},
    true,
  )
}

export function getControlTowerOperations(
  limit = 8,
): Promise<ControlTowerOperation[]> {
  return request<ControlTowerOperation[]>(
    `/api/v1/admin/control-tower/operations?limit=${limit}`,
    {},
    true,
  )
}

export function getControlTowerOperationTrace(
  operationId: string,
): Promise<ControlTowerOperationTrace> {
  return request<ControlTowerOperationTrace>(
    `/api/v1/admin/control-tower/operations/${operationId}`,
    {},
    true,
  )
}

export function getControlTowerDecisions(
  limit = 8,
): Promise<ControlTowerDecision[]> {
  return request<ControlTowerDecision[]>(
    `/api/v1/admin/control-tower/decisions?limit=${limit}`,
    {},
    true,
  )
}

export function getControlTowerDataOps(
  limit = 5,
): Promise<ControlTowerDataOps> {
  return request<ControlTowerDataOps>(
    `/api/v1/admin/control-tower/dataops?limit=${limit}`,
    {},
    true,
  )
}

export function runControlTowerDataOps(): Promise<ControlTowerActionResult> {
  return request<ControlTowerActionResult>(
    '/api/v1/admin/control-tower/actions/run-dataops',
    {
      method: 'POST',
    },
    true,
  )
}


export function runControlTowerQualityTest(): Promise<ControlTowerActionResult> {
  return request<ControlTowerActionResult>(
    '/api/v1/admin/control-tower/actions/run-quality-test',
    {
      method: 'POST',
    },
    true,
  )
}
// =====================================================
// Operational Copilot
// =====================================================

import type {
  CopilotAnalysisResponse,
  CopilotHistoryResponse,
  CopilotReviewPayload,
  CopilotReviewResponse,
} from './types'

export function analyzeControlTowerDataOps(
  runId: string,
): Promise<CopilotAnalysisResponse> {
  return request<CopilotAnalysisResponse>(
    `/api/v1/admin/copilot/dataops/${encodeURIComponent(runId)}/analyze`,
    {
      method: 'POST',
    },
    true,
  )
}

export function reviewControlTowerCopilot(
  correlationId: string,
  payload: CopilotReviewPayload,
): Promise<CopilotReviewResponse> {
  return jsonRequest<CopilotReviewResponse>(
    `/api/v1/admin/copilot/${encodeURIComponent(correlationId)}/review`,
    'POST',
    payload,
  )
}

export function getControlTowerCopilotHistory(
  limit = 20,
): Promise<CopilotHistoryResponse> {
  return request<CopilotHistoryResponse>(
    `/api/v1/admin/copilot/history?limit=${limit}`,
    {},
    true,
  )
}

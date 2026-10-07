export type UserRole = 'ADMIN' | 'CUSTOMER'

export interface AuthToken {
  access_token: string
  token_type: string
  expires_in: number
}

export interface CurrentUser {
  id: string
  email: string
  role: UserRole
  customer_id: string | null
}

export interface Customer {
  id: string
  customer_code: string
  full_name: string
  email: string
  region: string
  onboarding_status: 'PENDING' | 'VERIFIED' | 'REJECTED' | string
  created_at: string
}

export interface RegisterResponse {
  customer_id: string
  onboarding_status: string
  message: string
}

export type IdentityVerificationResult =
  | 'MATCH'
  | 'MISMATCH'
  | 'NOT_FOUND'
  | 'NOT_CURRENT'

export interface IdentityVerificationSummary {
  result: IdentityVerificationResult
  evidence_ref: string
  verified_at: string
}

export interface PendingOnboarding {
  customer_id: string
  customer_code: string
  full_name: string
  onboarding_status: string
  identity_verification: IdentityVerificationSummary | null
}

export interface IdentityVerificationResponse {
  verification_id: string
  customer_id: string
  result: IdentityVerificationResult
  evidence_ref: string
  document_status: 'CURRENT' | 'NOT_CURRENT' | null
  matched_name: boolean
  matched_birth_date: boolean
  verified_at: string
  synthetic: boolean
  source: 'RENIEC_SIMULATOR'
}

export interface ReviewPayload {
  decision: 'VERIFIED' | 'REJECTED'
  evidence_ref: string
  document_checked: boolean
  data_consistent: boolean
  notes: string
}

export interface ReviewResponse {
  customer_id: string
  onboarding_status: string
  review_id: string
  evidence_ref: string
  reniec_result: IdentityVerificationResult | null
  human_decision: boolean
  synthetic: boolean
}

export interface DatabaseHealth {
  database: string
  connection: string
}

export interface Account {
  id: string
  customer_id: string
  account_number: string
  account_type: string
  currency: 'PEN' | 'USD' | string
  balance: string
  status: string
  created_at: string
}

export interface Movement {
  id: string
  operation_id: string
  transaction_type: string
  direction: 'CREDIT' | 'DEBIT' | string
  amount: string
  currency: string
  balance_after: string
  created_at: string
}

export interface Card {
  id: string
  account_id: string
  card_reference: string
  last_four: string
  status: string
  created_at: string
}

export interface LoanApplication {
  id: string
  customer_id: string
  requested_amount: string
  currency: string
  term_months: number
  purpose: string | null
  disbursement_account_id: string | null
  status: string
  human_review_required: boolean
  requested_at: string
  reviewed_at: string | null
}

export interface OperationResult {
  operation_id: string
  status: string
  operation_type: string
  amount: string
  currency: string
  balances_after: Record<string, string>
  replayed: boolean
}


export type TransferScope =
  | 'OWN_ACCOUNTS'
  | 'BANCOCLOUD_THIRD_PARTY'
  | 'INTERBANK'

export type InterbankBankCode =
  | 'BCP'
  | 'INTERBANK'
  | 'BBVA'
  | 'SCOTIABANK'
  | 'BANBIF'
  | 'BANCO_NACION'

export interface ThirdPartyBeneficiary {
  holder_display: string
  account_last4: string
  account_type: string
  currency: string
}


export interface PendingLoanApplication {
  application_id: string
  customer_id: string
  customer_code: string
  full_name: string
  requested_amount: string
  currency: string
  term_months: number
  purpose: string | null
  disbursement_account_id: string | null
  disbursement_account_last4: string | null
  status: string
  human_review_required: boolean
  requested_at: string
}

export interface LoanAdminReviewPayload {
  decision: 'APPROVED' | 'REJECTED'
  annual_rate: number | null
  notes: string
}

export interface LoanAdminReviewResponse {
  application_id: string
  decision: string
  loan_id: string | null
  installments_created: number
  annual_rate: string | null
  disbursement_status: string | null
  scheduled_disbursement_at: string | null
  disbursement_account_last4: string | null
}

export interface LoanSummary {
  id: string
  customer_id: string
  loan_application_id: string | null
  principal: string | number
  currency: string
  annual_rate: string | number
  term_months: number
  status: string
  requested_at: string
  approved_at: string | null
  disbursement_status: string
  scheduled_disbursement_at: string | null
  disbursed_at: string | null
  disbursement_operation_id: string | null
  disbursement_account_id: string | null
  disbursement_account_last4: string | null
  installment_count: number
  installment_amount: string | number | null
  total_scheduled: string | number
  total_paid: string | number
  outstanding_amount: string | number
  next_due_date: string | null
  next_due_amount: string | number | null
}

export interface LoanInstallmentDetail {
  id: string
  loan_id: string
  installment_number: number
  due_date: string
  due_amount: string | number
  paid_amount: string | number
  outstanding_amount: string | number
  status: string
}

// =====================================================
// Operations Control Tower
// =====================================================

export interface ControlTowerDataOpsRun {
  run_id: string
  pipeline_name: string
  status: string
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  rows_extracted: number
  rows_accepted: number
  rows_quarantined: number
  quality_total: number
  quality_passed: number
  quality_failed: number
  quarantine_records: number
  publication_status: string | null
  is_current_gold: boolean
  published_at: string | null
  gold_row_count: number | null
  error_message: string | null
}

export interface ControlTowerGold {
  batch_id: string
  source_run_id: string
  publication_status: string
  gold_row_count: number
  quality_gate_total: number
  quality_gate_passed: number
  rows_quarantined: number
  published_at: string | null
  pipeline_name: string
  pipeline_status: string
  rows_extracted: number
  rows_accepted: number
}

export interface ControlTowerOverview {
  api: string
  postgresql: string
  admin: {
    id: string
    email: string
    role: string
  }
  latest_dataops_run: ControlTowerDataOpsRun | null
  current_gold: ControlTowerGold | null
  counts: {
    banking_operations: number
    audit_events: number
    ledger_entries: number
    transactions: number
    quarantine_records: number
    pending_onboarding: number
    pending_loans: number
  }
}

export interface ControlTowerOperation {
  operation_id: string
  operation_type: string
  status: string
  amount: number
  currency: string
  source_account_id: string | null
  target_account_id: string | null
  created_at: string
  completed_at: string | null
  source_customer_code: string | null
  target_customer_code: string | null
  transaction_count: number
  ledger_entry_count: number
  correlation_id: string | null
  actor_type: string | null
  actor_id: string | null
  actor_email: string | null
}

export interface ControlTowerDecision {
  audit_event_id: string
  correlation_id: string
  action: string
  actor_type: string
  result: string
  entity_type: string
  entity_id: string
  decision: string | null
  reviewer_id: string | null
  reviewer_email: string | null
  reviewer_role: string | null
  subject_name: string | null
  subject_code: string | null
  evidence_ref: string | null
  reniec_result: string | null
  loan_id: string | null
  disbursement_status: string | null
  scheduled_disbursement_at: string | null
  disbursed_at: string | null
  tea_percent: string | null
  human_decision: string | null
  llm_decision: string | null
  occurred_at: string
}

export interface ControlTowerTraceTransaction {
  transaction_id: string
  account_id: string
  account_last4: string | null
  loan_id: string | null
  transaction_type: string
  direction: string
  amount: number
  currency: string
  balance_after: number
  description: string | null
  created_at: string
}

export interface ControlTowerLedgerEntry {
  ledger_entry_id: string
  sequence_no: number
  account_id: string | null
  clearing_account_code: string | null
  direction: string
  amount: number
  currency: string
  created_at: string
}

export interface ControlTowerAuditEvent {
  audit_event_id: string
  correlation_id: string
  actor_type: string
  action: string
  entity_type: string
  entity_id: string | null
  result: string
  details: Record<string, unknown>
  occurred_at: string
  actor_email: string | null
}

export interface ControlTowerLineage {
  operation_key: number
  source_operation_id: string
  operation_type: string
  status: string
  amount: number
  currency: string
  transaction_count: number
  debit_amount: number
  credit_amount: number
  last_run_id: string
  batch_id: string | null
  publication_status: string | null
  is_current: boolean | null
  gold_row_count: number | null
  quality_gate_total: number | null
  quality_gate_passed: number | null
  rows_quarantined: number | null
  published_at: string | null
}

export interface ControlTowerOperationTrace {
  operation: {
    operation_id: string
    idempotency_key: string
    operation_type: string
    status: string
    source_account_id: string | null
    target_account_id: string | null
    amount: number
    currency: string
    created_at: string
    completed_at: string | null
  }
  transactions: ControlTowerTraceTransaction[]
  ledger: ControlTowerLedgerEntry[]
  audit: ControlTowerAuditEvent[]
  lineage: ControlTowerLineage | null
}

export interface ControlTowerQuarantineItem {
  run_id: string
  pipeline_name: string
  pipeline_status: string
  source_table: string
  rule_name: string
  reason: string
  rejected_records: number
}

export interface ControlTowerDataOps {
  runs: ControlTowerDataOpsRun[]
  current_gold: ControlTowerGold | null
  quarantine: ControlTowerQuarantineItem[]
}

export interface ControlTowerActionResult {
  action: 'RUN_DATAOPS' | 'RUN_QUALITY_TEST' | string
  run_id: string
  status: string
  published: boolean
  gold_protected?: boolean
  message: string
}
// =====================================================
// Operational Copilot
// =====================================================

export interface CopilotAnalysis {
  summary: string
  category: string
  evidence: string[]
  risk_flags: string[]
  missing_information: string[]
  recommended_next_step: string
  confidence: number
  human_review_required: boolean
}

export interface CopilotAnalysisResponse {
  correlation_id: string
  status: string
  prompt_version: string
  model: string
  analysis: CopilotAnalysis
  human_review_status: 'PENDING' | 'COMPLETED' | string
}

export interface CopilotReviewPayload {
  decision: 'ACKNOWLEDGED'
  notes: string
}

export interface CopilotReviewResponse {
  correlation_id: string
  decision: string
  reviewed_by: string
  human_review_status: 'COMPLETED' | string
}

export interface CopilotHumanReview {
  decision: string
  reviewer_id: string | null
  reviewer_email: string | null
  notes: string | null
  reviewed_at: string | null
}

export interface CopilotHistoryItem {
  correlation_id: string
  source_entity_type: string
  source_entity_id: string | null
  created_at: string
  prompt_version: string | null
  model: string | null
  category: string | null
  confidence: number | null
  human_review_required: boolean
  analysis: CopilotAnalysis | null
  human_review_status: 'PENDING' | 'COMPLETED' | string
  human_review: CopilotHumanReview | null
}

export interface CopilotHistoryResponse {
  value: CopilotHistoryItem[]
  Count: number
}

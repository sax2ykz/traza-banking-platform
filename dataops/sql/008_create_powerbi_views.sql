BEGIN;


-- ============================================================
-- 1. OPERACIONES MENSUALES
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_operations_monthly AS
SELECT
    t.dataset_version,

    DATE_TRUNC(
        'month',
        d.full_date
    )::DATE AS period_month,

    d.year,
    d.month AS month_number,
    d.month_name,

    c.region,
    c.segment,

    t.operation_type,
    t.channel,

    COUNT(*) AS total_transactions,

    COUNT(*) FILTER (
        WHERE t.status = 'COMPLETED'
    ) AS completed_transactions,

    COUNT(*) FILTER (
        WHERE t.status = 'REJECTED'
    ) AS rejected_transactions,

    ROUND(
        (
            100.0
            * COUNT(*) FILTER (
                WHERE t.status = 'COMPLETED'
            )
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS success_rate_pct,

    COALESCE(
        SUM(t.amount) FILTER (
            WHERE t.status = 'COMPLETED'
        ),
        0
    ) AS completed_amount,

    COALESCE(
        SUM(t.amount) FILTER (
            WHERE t.status = 'REJECTED'
        ),
        0
    ) AS rejected_amount,

    COALESCE(
        SUM(t.fee_amount) FILTER (
            WHERE t.status = 'COMPLETED'
        ),
        0
    ) AS fee_income

FROM analytics.synthetic_transactions t

JOIN analytics.synthetic_customers c
    ON c.customer_id = t.customer_id

JOIN analytics.dim_date d
    ON d.date_key = t.date_key

GROUP BY
    t.dataset_version,
    DATE_TRUNC('month', d.full_date)::DATE,
    d.year,
    d.month,
    d.month_name,
    c.region,
    c.segment,
    t.operation_type,
    t.channel;


-- ============================================================
-- 2. CARTERA DE CREDITOS A NIVEL PRESTAMO
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_credit_portfolio AS
WITH installment_summary AS (
    SELECT
        i.loan_id,

        COUNT(*) AS total_installments,

        COUNT(*) FILTER (
            WHERE i.status = 'PAID'
        ) AS paid_installments,

        COUNT(*) FILTER (
            WHERE i.days_past_due > 0
              AND i.outstanding_amount > 0
        ) AS overdue_installments,

        COALESCE(
            MAX(i.days_past_due),
            0
        ) AS max_days_past_due,

        COALESCE(
            SUM(i.outstanding_amount),
            0
        ) AS schedule_outstanding_amount,

        COALESCE(
            SUM(i.outstanding_amount) FILTER (
                WHERE i.days_past_due > 0
            ),
            0
        ) AS overdue_amount

    FROM analytics.synthetic_loan_installments i

    GROUP BY i.loan_id
)

SELECT
    l.dataset_version,
    l.loan_id,
    l.customer_id,

    c.region,
    c.segment,

    d.full_date AS origination_date,

    l.principal,
    l.annual_rate,
    l.term_months,
    l.current_balance,

    l.status AS loan_status,

    COALESCE(
        i.total_installments,
        0
    ) AS total_installments,

    COALESCE(
        i.paid_installments,
        0
    ) AS paid_installments,

    COALESCE(
        i.overdue_installments,
        0
    ) AS overdue_installments,

    COALESCE(
        i.max_days_past_due,
        0
    ) AS max_days_past_due,

    CASE
        WHEN COALESCE(i.max_days_past_due, 0) = 0
            THEN 'AL_DIA'

        WHEN i.max_days_past_due BETWEEN 1 AND 30
            THEN '1_30'

        WHEN i.max_days_past_due BETWEEN 31 AND 60
            THEN '31_60'

        WHEN i.max_days_past_due BETWEEN 61 AND 90
            THEN '61_90'

        ELSE '90_PLUS'
    END AS delinquency_bucket,

    COALESCE(
        i.overdue_amount,
        0
    ) AS overdue_amount,

    COALESCE(
        i.schedule_outstanding_amount,
        0
    ) AS schedule_outstanding_amount,

    (
        COALESCE(i.max_days_past_due, 0) > 0
    ) AS is_delinquent

FROM analytics.synthetic_loans l

JOIN analytics.synthetic_customers c
    ON c.customer_id = l.customer_id

JOIN analytics.dim_date d
    ON d.date_key = l.origination_date_key

LEFT JOIN installment_summary i
    ON i.loan_id = l.loan_id;


-- ============================================================
-- 3. MOROSIDAD POR BUCKET
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_delinquency_by_bucket AS
SELECT
    dataset_version,
    region,
    segment,
    delinquency_bucket,

    COUNT(*) AS loans,

    SUM(current_balance)
        AS portfolio_balance,

    SUM(overdue_amount)
        AS overdue_balance,

    ROUND(
        AVG(max_days_past_due)::NUMERIC,
        2
    ) AS avg_days_past_due

FROM analytics.vw_credit_portfolio

GROUP BY
    dataset_version,
    region,
    segment,
    delinquency_bucket;


-- ============================================================
-- 4. RENTABILIDAD MENSUAL
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_profitability_monthly AS
SELECT
    p.dataset_version,

    d.full_date AS period_month,
    d.year,
    d.month AS month_number,
    d.month_name,

    p.segment,
    p.product,

    p.active_customers,
    p.transaction_count,
    p.transaction_amount,

    p.outstanding_balance,

    p.interest_income,
    p.fee_income,

    (
        p.interest_income
        + p.fee_income
    ) AS total_income,

    p.funding_cost,
    p.allocated_operating_cost,

    p.estimated_operating_margin,

    ROUND(
        (
            100.0
            * p.estimated_operating_margin
            / NULLIF(
                p.interest_income
                + p.fee_income,
                0
            )
        )::NUMERIC,
        2
    ) AS operating_margin_pct

FROM analytics.synthetic_profitability_monthly p

JOIN analytics.dim_date d
    ON d.date_key = p.period_month_key;


-- ============================================================
-- 5. ESTADO DE EJECUCIONES DATAOPS
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_dataops_runs AS
WITH quality AS (
    SELECT
        run_id,

        COUNT(*) AS quality_total,

        COUNT(*) FILTER (
            WHERE passed = TRUE
        ) AS quality_passed,

        COUNT(*) FILTER (
            WHERE passed = FALSE
        ) AS quality_failed

    FROM dataops.quality_results

    GROUP BY run_id
),

quarantine_summary AS (
    SELECT
        run_id,
        COUNT(*) AS quarantine_records

    FROM quarantine.rejected_records

    GROUP BY run_id
)

SELECT
    r.run_id,
    r.pipeline_name,
    r.status,

    r.started_at,
    r.finished_at,

    CASE
        WHEN r.finished_at IS NOT NULL
        THEN ROUND(
            EXTRACT(
                EPOCH FROM (
                    r.finished_at
                    - r.started_at
                )
            )::NUMERIC,
            3
        )
    END AS duration_seconds,

    r.rows_extracted,
    r.rows_accepted,
    r.rows_quarantined,

    COALESCE(
        q.quality_total,
        0
    ) AS quality_total,

    COALESCE(
        q.quality_passed,
        0
    ) AS quality_passed,

    COALESCE(
        q.quality_failed,
        0
    ) AS quality_failed,

    COALESCE(
        qs.quarantine_records,
        0
    ) AS quarantine_records,

    pb.publication_status,

    COALESCE(
        pb.is_current,
        FALSE
    ) AS is_current_gold,

    pb.published_at,
    pb.gold_row_count,

    r.error_message

FROM dataops.pipeline_runs r

LEFT JOIN quality q
    ON q.run_id = r.run_id

LEFT JOIN quarantine_summary qs
    ON qs.run_id = r.run_id

LEFT JOIN dataops.published_batches pb
    ON pb.source_run_id = r.run_id;


-- ============================================================
-- 6. RESUMEN DE QUARANTINE
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_quarantine_summary AS
SELECT
    q.run_id,

    r.pipeline_name,
    r.status AS pipeline_status,

    q.source_table,
    q.rule_name,
    q.reason,

    COUNT(*) AS rejected_records

FROM quarantine.rejected_records q

JOIN dataops.pipeline_runs r
    ON r.run_id = q.run_id

GROUP BY
    q.run_id,
    r.pipeline_name,
    r.status,
    q.source_table,
    q.rule_name,
    q.reason;


-- ============================================================
-- 7. GOLD ACTUAL
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_current_gold_status AS
SELECT
    pb.batch_id,
    pb.source_run_id,

    pb.publication_status,
    pb.gold_row_count,

    pb.quality_gate_total,
    pb.quality_gate_passed,

    pb.rows_quarantined,

    pb.published_at,

    r.pipeline_name,
    r.status AS pipeline_status,
    r.rows_extracted,
    r.rows_accepted

FROM dataops.current_published_batch pb

JOIN dataops.pipeline_runs r
    ON r.run_id = pb.source_run_id;


-- ============================================================
-- 8. OPERACIONES DEL GOLD VIGENTE
-- ============================================================

CREATE OR REPLACE VIEW analytics.vw_current_gold_operations AS
SELECT
    o.operation_type,
    o.status,

    COUNT(*) AS operations,

    SUM(o.amount)
        AS operation_amount,

    SUM(o.debit_amount)
        AS debit_amount,

    SUM(o.credit_amount)
        AS credit_amount,

    SUM(o.transaction_count)
        AS transaction_rows,

    cp.batch_id,
    cp.source_run_id

FROM dw.fact_banking_operations o

JOIN dataops.current_published_batch cp
    ON cp.source_run_id = o.last_run_id

GROUP BY
    o.operation_type,
    o.status,
    cp.batch_id,
    cp.source_run_id;


COMMIT;

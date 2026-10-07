CREATE OR REPLACE FUNCTION dataops.publish_gold(p_run_id UUID)
RETURNS TABLE (
    batch_id UUID,
    source_run_id UUID,
    publication_state TEXT,
    gold_row_count INTEGER,
    quality_total INTEGER,
    quality_passed INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status VARCHAR(30);
    v_rows_extracted INTEGER;
    v_rows_accepted INTEGER;
    v_rows_quarantined INTEGER;

    v_quality_total INTEGER;
    v_quality_passed INTEGER;

    v_stage_count INTEGER;
    v_quarantine_count INTEGER;
    v_date_count INTEGER;
    v_gold_count INTEGER;

    v_operation_mismatches INTEGER;
BEGIN

    ----------------------------------------------------------------
    -- 1. VALIDAR QUE EL RUN EXISTE
    ----------------------------------------------------------------

    SELECT
        pr.status,
        pr.rows_extracted,
        pr.rows_accepted,
        pr.rows_quarantined
    INTO
        v_status,
        v_rows_extracted,
        v_rows_accepted,
        v_rows_quarantined
    FROM dataops.pipeline_runs pr
    WHERE pr.run_id = p_run_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Run % no existe en dataops.pipeline_runs',
            p_run_id;
    END IF;


    ----------------------------------------------------------------
    -- 2. IDEMPOTENCIA DE PUBLICACION
    ----------------------------------------------------------------

    IF EXISTS (
        SELECT 1
        FROM dataops.published_batches pb
        WHERE pb.source_run_id = p_run_id
          AND pb.publication_status = 'PUBLISHED'
    ) THEN

        RETURN QUERY
        SELECT
            pb.batch_id,
            pb.source_run_id,
            pb.publication_status::TEXT,
            pb.gold_row_count,
            pb.quality_gate_total,
            pb.quality_gate_passed
        FROM dataops.published_batches pb
        WHERE pb.source_run_id = p_run_id;

        RETURN;
    END IF;


    ----------------------------------------------------------------
    -- 3. QUALITY GATES
    ----------------------------------------------------------------

    SELECT
        COUNT(*)::INTEGER,
        COUNT(*) FILTER (WHERE qr.passed = TRUE)::INTEGER
    INTO
        v_quality_total,
        v_quality_passed
    FROM dataops.quality_results qr
    WHERE qr.run_id = p_run_id;


    IF v_status <> 'SUCCEEDED' THEN
        RAISE EXCEPTION
            'Run % no publicable. Estado actual: %',
            p_run_id,
            v_status;
    END IF;


    IF v_quality_total = 0 THEN
        RAISE EXCEPTION
            'Run % no posee Quality Gates',
            p_run_id;
    END IF;


    IF v_quality_passed <> v_quality_total THEN
        RAISE EXCEPTION
            'Run % no publicable. Quality Gates: %/%',
            p_run_id,
            v_quality_passed,
            v_quality_total;
    END IF;


    ----------------------------------------------------------------
    -- 4. RECONCILIACION SILVER
    ----------------------------------------------------------------

    SELECT SUM(x.rows_count)::INTEGER
    INTO v_stage_count
    FROM (
        SELECT COUNT(*) AS rows_count
        FROM staging.customers
        WHERE run_id = p_run_id

        UNION ALL

        SELECT COUNT(*)
        FROM staging.accounts
        WHERE run_id = p_run_id

        UNION ALL

        SELECT COUNT(*)
        FROM staging.transactions
        WHERE run_id = p_run_id

        UNION ALL

        SELECT COUNT(*)
        FROM staging.banking_operations
        WHERE run_id = p_run_id

        UNION ALL

        SELECT COUNT(*)
        FROM staging.loan_applications
        WHERE run_id = p_run_id

        UNION ALL

        SELECT COUNT(*)
        FROM staging.loans
        WHERE run_id = p_run_id

        UNION ALL

        SELECT COUNT(*)
        FROM staging.loan_installments
        WHERE run_id = p_run_id

        UNION ALL

        SELECT COUNT(*)
        FROM staging.loan_payments
        WHERE run_id = p_run_id
    ) x;


    SELECT COUNT(*)::INTEGER
    INTO v_quarantine_count
    FROM quarantine.rejected_records qr
    WHERE qr.run_id = p_run_id;


    IF v_stage_count <> v_rows_accepted THEN
        RAISE EXCEPTION
            'Reconciliacion Silver fallida. Esperado accepted=%, Silver=%',
            v_rows_accepted,
            v_stage_count;
    END IF;


    IF v_quarantine_count <> v_rows_quarantined THEN
        RAISE EXCEPTION
            'Reconciliacion Quarantine fallida. Pipeline=%, tabla=%',
            v_rows_quarantined,
            v_quarantine_count;
    END IF;


    IF v_rows_extracted <> v_stage_count + v_quarantine_count THEN
        RAISE EXCEPTION
            'Reconciliacion total fallida. Extracted=%, Silver+Quarantine=%',
            v_rows_extracted,
            v_stage_count + v_quarantine_count;
    END IF;


    IF v_rows_quarantined <> 0 THEN
        RAISE EXCEPTION
            'Run % no publicable: contiene % registros en Quarantine',
            p_run_id,
            v_rows_quarantined;
    END IF;


    ----------------------------------------------------------------
    -- 5. DIM_DATE
    ----------------------------------------------------------------

    WITH source_dates AS (

        SELECT created_at::DATE AS full_date
        FROM staging.customers
        WHERE run_id = p_run_id

        UNION

        SELECT created_at::DATE
        FROM staging.accounts
        WHERE run_id = p_run_id

        UNION

        SELECT created_at::DATE
        FROM staging.transactions
        WHERE run_id = p_run_id

        UNION

        SELECT created_at::DATE
        FROM staging.banking_operations
        WHERE run_id = p_run_id

        UNION

        SELECT completed_at::DATE
        FROM staging.banking_operations
        WHERE run_id = p_run_id
          AND completed_at IS NOT NULL

        UNION

        SELECT requested_at::DATE
        FROM staging.loan_applications
        WHERE run_id = p_run_id

        UNION

        SELECT reviewed_at::DATE
        FROM staging.loan_applications
        WHERE run_id = p_run_id
          AND reviewed_at IS NOT NULL

        UNION

        SELECT requested_at::DATE
        FROM staging.loans
        WHERE run_id = p_run_id

        UNION

        SELECT due_date
        FROM staging.loan_installments
        WHERE run_id = p_run_id

        UNION

        SELECT paid_at::DATE
        FROM staging.loan_payments
        WHERE run_id = p_run_id
          AND paid_at IS NOT NULL
    )

    INSERT INTO dw.dim_date (
        date_key,
        full_date,
        year,
        quarter,
        month,
        month_name,
        day,
        weekday,
        is_weekend
    )
    SELECT
        TO_CHAR(d.full_date, 'YYYYMMDD')::INTEGER,
        d.full_date,
        EXTRACT(YEAR FROM d.full_date)::INTEGER,
        EXTRACT(QUARTER FROM d.full_date)::INTEGER,
        EXTRACT(MONTH FROM d.full_date)::INTEGER,
        TRIM(TO_CHAR(d.full_date, 'Month')),
        EXTRACT(DAY FROM d.full_date)::INTEGER,
        EXTRACT(ISODOW FROM d.full_date)::INTEGER,
        EXTRACT(ISODOW FROM d.full_date)::INTEGER IN (6,7)
    FROM source_dates d
    WHERE d.full_date IS NOT NULL
    ON CONFLICT (full_date) DO NOTHING;


    ----------------------------------------------------------------
    -- 6. DIM_CUSTOMER
    ----------------------------------------------------------------

    INSERT INTO dw.dim_customer (
        source_customer_id,
        customer_code,
        region,
        onboarding_status,
        segment,
        created_at,
        last_run_id
    )
    SELECT
        s.customer_id,
        s.customer_code,
        s.region,
        s.onboarding_status,
        'NO_DEFINIDO',
        s.created_at,
        p_run_id
    FROM staging.customers s
    WHERE s.run_id = p_run_id

    ON CONFLICT (source_customer_id)
    DO UPDATE SET
        customer_code = EXCLUDED.customer_code,
        region = EXCLUDED.region,
        onboarding_status = EXCLUDED.onboarding_status,
        created_at = EXCLUDED.created_at,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 7. DIM_ACCOUNT
    ----------------------------------------------------------------

    INSERT INTO dw.dim_account (
        source_account_id,
        customer_key,
        account_last4,
        account_type,
        currency,
        status,
        opened_at,
        last_run_id
    )
    SELECT
        s.account_id,
        c.customer_key,
        s.account_last4,
        s.account_type,
        s.currency,
        s.status,
        s.created_at,
        p_run_id
    FROM staging.accounts s

    JOIN dw.dim_customer c
      ON c.source_customer_id = s.customer_id

    WHERE s.run_id = p_run_id

    ON CONFLICT (source_account_id)
    DO UPDATE SET
        customer_key = EXCLUDED.customer_key,
        account_last4 = EXCLUDED.account_last4,
        account_type = EXCLUDED.account_type,
        currency = EXCLUDED.currency,
        status = EXCLUDED.status,
        opened_at = EXCLUDED.opened_at,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 8. FACT_BANKING_OPERATIONS
    ----------------------------------------------------------------

    WITH operation_aggregation AS (
        SELECT
            t.operation_id,

            COUNT(*)::INTEGER AS transaction_count,

            COALESCE(
                SUM(t.amount)
                    FILTER (WHERE t.direction = 'DEBIT'),
                0
            ) AS debit_amount,

            COALESCE(
                SUM(t.amount)
                    FILTER (WHERE t.direction = 'CREDIT'),
                0
            ) AS credit_amount

        FROM staging.transactions t
        WHERE t.run_id = p_run_id

        GROUP BY t.operation_id
    )

    INSERT INTO dw.fact_banking_operations (
        source_operation_id,
        created_date_key,
        completed_date_key,
        source_account_key,
        target_account_key,
        operation_type,
        status,
        amount,
        currency,
        transaction_count,
        debit_amount,
        credit_amount,
        created_at,
        completed_at,
        last_run_id
    )
    SELECT
        bo.operation_id,

        TO_CHAR(
            bo.created_at::DATE,
            'YYYYMMDD'
        )::INTEGER,

        CASE
            WHEN bo.completed_at IS NOT NULL
            THEN TO_CHAR(
                bo.completed_at::DATE,
                'YYYYMMDD'
            )::INTEGER
        END,

        source_account.account_key,
        target_account.account_key,

        bo.operation_type,
        bo.status,
        bo.amount,
        bo.currency,

        COALESCE(a.transaction_count, 0),
        COALESCE(a.debit_amount, 0),
        COALESCE(a.credit_amount, 0),

        bo.created_at,
        bo.completed_at,
        p_run_id

    FROM staging.banking_operations bo

    LEFT JOIN operation_aggregation a
      ON a.operation_id = bo.operation_id

    LEFT JOIN dw.dim_account source_account
      ON source_account.source_account_id =
         bo.source_account_id

    LEFT JOIN dw.dim_account target_account
      ON target_account.source_account_id =
         bo.target_account_id

    WHERE bo.run_id = p_run_id

    ON CONFLICT (source_operation_id)
    DO UPDATE SET
        created_date_key = EXCLUDED.created_date_key,
        completed_date_key = EXCLUDED.completed_date_key,
        source_account_key = EXCLUDED.source_account_key,
        target_account_key = EXCLUDED.target_account_key,
        operation_type = EXCLUDED.operation_type,
        status = EXCLUDED.status,
        amount = EXCLUDED.amount,
        currency = EXCLUDED.currency,
        transaction_count = EXCLUDED.transaction_count,
        debit_amount = EXCLUDED.debit_amount,
        credit_amount = EXCLUDED.credit_amount,
        created_at = EXCLUDED.created_at,
        completed_at = EXCLUDED.completed_at,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 9. FACT_TRANSACTIONS
    ----------------------------------------------------------------

    INSERT INTO dw.fact_transactions (
        source_transaction_id,
        date_key,
        customer_key,
        account_key,
        source_loan_id,
        source_operation_id,
        transaction_type,
        direction,
        amount,
        currency,
        balance_after,
        last_run_id
    )
    SELECT
        t.transaction_id,

        TO_CHAR(
            t.created_at::DATE,
            'YYYYMMDD'
        )::INTEGER,

        a.customer_key,
        a.account_key,
        t.loan_id,

        t.operation_id,
        t.transaction_type,
        t.direction,
        t.amount,
        t.currency,
        t.balance_after,
        p_run_id

    FROM staging.transactions t

    JOIN dw.dim_account a
      ON a.source_account_id = t.account_id

    WHERE t.run_id = p_run_id

    ON CONFLICT (source_transaction_id)
    DO UPDATE SET
        date_key = EXCLUDED.date_key,
        customer_key = EXCLUDED.customer_key,
        account_key = EXCLUDED.account_key,
        source_loan_id = EXCLUDED.source_loan_id,
        source_operation_id = EXCLUDED.source_operation_id,
        transaction_type = EXCLUDED.transaction_type,
        direction = EXCLUDED.direction,
        amount = EXCLUDED.amount,
        currency = EXCLUDED.currency,
        balance_after = EXCLUDED.balance_after,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 10. FACT_LOAN_APPLICATIONS
    ----------------------------------------------------------------

    INSERT INTO dw.fact_loan_applications (
        source_application_id,
        date_key,
        customer_key,
        requested_amount,
        currency,
        term_months,
        purpose,
        status,
        human_review_required,
        reviewed_at,
        last_run_id
    )
    SELECT
        la.application_id,

        TO_CHAR(
            la.requested_at::DATE,
            'YYYYMMDD'
        )::INTEGER,

        c.customer_key,

        la.requested_amount,
        la.currency,
        la.term_months,
        la.purpose,
        la.status,
        la.human_review_required,
        la.reviewed_at,
        p_run_id

    FROM staging.loan_applications la

    JOIN dw.dim_customer c
      ON c.source_customer_id = la.customer_id

    WHERE la.run_id = p_run_id

    ON CONFLICT (source_application_id)
    DO UPDATE SET
        date_key = EXCLUDED.date_key,
        customer_key = EXCLUDED.customer_key,
        requested_amount = EXCLUDED.requested_amount,
        currency = EXCLUDED.currency,
        term_months = EXCLUDED.term_months,
        purpose = EXCLUDED.purpose,
        status = EXCLUDED.status,
        human_review_required = EXCLUDED.human_review_required,
        reviewed_at = EXCLUDED.reviewed_at,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 11. FACT_LOANS
    ----------------------------------------------------------------

    INSERT INTO dw.fact_loans (
        source_loan_id,
        date_key,
        customer_key,
        source_application_id,
        principal,
        annual_rate,
        term_months,
        status,
        last_run_id
    )
    SELECT
        l.loan_id,

        TO_CHAR(
            l.requested_at::DATE,
            'YYYYMMDD'
        )::INTEGER,

        c.customer_key,

        l.loan_application_id,
        l.principal,
        l.annual_rate,
        l.term_months,
        l.status,
        p_run_id

    FROM staging.loans l

    JOIN dw.dim_customer c
      ON c.source_customer_id = l.customer_id

    WHERE l.run_id = p_run_id

    ON CONFLICT (source_loan_id)
    DO UPDATE SET
        date_key = EXCLUDED.date_key,
        customer_key = EXCLUDED.customer_key,
        source_application_id = EXCLUDED.source_application_id,
        principal = EXCLUDED.principal,
        annual_rate = EXCLUDED.annual_rate,
        term_months = EXCLUDED.term_months,
        status = EXCLUDED.status,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 12. FACT_LOAN_INSTALLMENTS
    ----------------------------------------------------------------

    WITH installment_base AS (
        SELECT
            li.*,

            GREATEST(
                li.due_amount - COALESCE(li.paid_amount, 0),
                0
            ) AS outstanding_amount,

            CASE
                WHEN li.due_date < CURRENT_DATE
                 AND GREATEST(
                        li.due_amount -
                        COALESCE(li.paid_amount, 0),
                        0
                     ) > 0
                THEN CURRENT_DATE - li.due_date
                ELSE 0
            END AS days_past_due

        FROM staging.loan_installments li
        WHERE li.run_id = p_run_id
    )

    INSERT INTO dw.fact_loan_installments (
        source_installment_id,
        loan_key,
        due_date_key,
        installment_number,
        due_amount,
        paid_amount,
        outstanding_amount,
        days_past_due,
        delinquency_bucket,
        status,
        last_run_id
    )
    SELECT
        i.installment_id,
        l.loan_key,

        TO_CHAR(
            i.due_date,
            'YYYYMMDD'
        )::INTEGER,

        i.installment_number,
        i.due_amount,
        COALESCE(i.paid_amount, 0),
        i.outstanding_amount,
        i.days_past_due,

        CASE
            WHEN i.days_past_due = 0
                THEN 'AL_DIA'
            WHEN i.days_past_due BETWEEN 1 AND 30
                THEN '1_30'
            WHEN i.days_past_due BETWEEN 31 AND 60
                THEN '31_60'
            WHEN i.days_past_due BETWEEN 61 AND 90
                THEN '61_90'
            ELSE '90_PLUS'
        END,

        i.status,
        p_run_id

    FROM installment_base i

    JOIN dw.fact_loans l
      ON l.source_loan_id = i.loan_id

    ON CONFLICT (source_installment_id)
    DO UPDATE SET
        loan_key = EXCLUDED.loan_key,
        due_date_key = EXCLUDED.due_date_key,
        installment_number = EXCLUDED.installment_number,
        due_amount = EXCLUDED.due_amount,
        paid_amount = EXCLUDED.paid_amount,
        outstanding_amount = EXCLUDED.outstanding_amount,
        days_past_due = EXCLUDED.days_past_due,
        delinquency_bucket = EXCLUDED.delinquency_bucket,
        status = EXCLUDED.status,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 13. FACT_LOAN_PAYMENTS
    ----------------------------------------------------------------

    INSERT INTO dw.fact_loan_payments (
        source_payment_id,
        payment_date_key,
        installment_key,
        source_operation_id,
        amount,
        status,
        last_run_id
    )
    SELECT
        p.payment_id,

        TO_CHAR(
            p.paid_at::DATE,
            'YYYYMMDD'
        )::INTEGER,

        i.installment_key,

        p.operation_id,
        p.amount,
        p.status,
        p_run_id

    FROM staging.loan_payments p

    JOIN dw.fact_loan_installments i
      ON i.source_installment_id =
         p.installment_id

    WHERE p.run_id = p_run_id

    ON CONFLICT (source_payment_id)
    DO UPDATE SET
        payment_date_key = EXCLUDED.payment_date_key,
        installment_key = EXCLUDED.installment_key,
        source_operation_id = EXCLUDED.source_operation_id,
        amount = EXCLUDED.amount,
        status = EXCLUDED.status,
        last_run_id = EXCLUDED.last_run_id;


    ----------------------------------------------------------------
    -- 14. RECONCILIACION DE CONTEOS GOLD
    ----------------------------------------------------------------

    IF (
        SELECT COUNT(*)
        FROM dw.dim_customer
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.customers
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: customers';
    END IF;


    IF (
        SELECT COUNT(*)
        FROM dw.dim_account
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.accounts
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: accounts';
    END IF;


    IF (
        SELECT COUNT(*)
        FROM dw.fact_banking_operations
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.banking_operations
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: banking_operations';
    END IF;


    IF (
        SELECT COUNT(*)
        FROM dw.fact_transactions
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.transactions
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: transactions';
    END IF;


    IF (
        SELECT COUNT(*)
        FROM dw.fact_loan_applications
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.loan_applications
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: loan_applications';
    END IF;


    IF (
        SELECT COUNT(*)
        FROM dw.fact_loans
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.loans
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: loans';
    END IF;


    IF (
        SELECT COUNT(*)
        FROM dw.fact_loan_installments
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.loan_installments
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: loan_installments';
    END IF;


    IF (
        SELECT COUNT(*)
        FROM dw.fact_loan_payments
        WHERE last_run_id = p_run_id
    ) <> (
        SELECT COUNT(*)
        FROM staging.loan_payments
        WHERE run_id = p_run_id
    ) THEN
        RAISE EXCEPTION
            'Gold reconciliation failed: loan_payments';
    END IF;


    ----------------------------------------------------------------
    -- 15. RECONCILIACION FINANCIERA DE OPERACIONES
    ----------------------------------------------------------------

    SELECT COUNT(*)::INTEGER
    INTO v_operation_mismatches
    FROM dw.fact_banking_operations o
    WHERE o.last_run_id = p_run_id
      AND o.status = 'COMPLETED'
      AND (
            (
                o.operation_type = 'DEPOSIT'
                AND NOT (
                    o.transaction_count = 1
                    AND o.debit_amount = 0
                    AND o.credit_amount = o.amount
                )
            )

            OR

            (
                o.operation_type = 'WITHDRAWAL'
                AND NOT (
                    o.transaction_count = 1
                    AND o.debit_amount = o.amount
                    AND o.credit_amount = 0
                )
            )

            OR

            (
                o.operation_type = 'TRANSFER'
                AND NOT (
                    o.transaction_count = 2
                    AND o.debit_amount = o.amount
                    AND o.credit_amount = o.amount
                )
            )

            OR

            (
                o.operation_type = 'LOAN_DISBURSEMENT'
                AND NOT (
                    o.transaction_count = 1
                    AND o.debit_amount = 0
                    AND o.credit_amount = o.amount
                    AND o.target_account_key IS NOT NULL
                )
            )

            OR

            o.operation_type NOT IN (
                'DEPOSIT',
                'WITHDRAWAL',
                'TRANSFER',
                'LOAN_DISBURSEMENT'
            )
      );


    IF v_operation_mismatches <> 0 THEN
        RAISE EXCEPTION
            'Gold financial reconciliation failed: % operations',
            v_operation_mismatches;
    END IF;


    ----------------------------------------------------------------
    -- 16. CALCULAR FILAS GOLD
    ----------------------------------------------------------------

    WITH source_dates AS (

        SELECT created_at::DATE AS full_date
        FROM staging.customers
        WHERE run_id = p_run_id

        UNION

        SELECT created_at::DATE
        FROM staging.accounts
        WHERE run_id = p_run_id

        UNION

        SELECT created_at::DATE
        FROM staging.transactions
        WHERE run_id = p_run_id

        UNION

        SELECT created_at::DATE
        FROM staging.banking_operations
        WHERE run_id = p_run_id

        UNION

        SELECT completed_at::DATE
        FROM staging.banking_operations
        WHERE run_id = p_run_id
          AND completed_at IS NOT NULL

        UNION

        SELECT requested_at::DATE
        FROM staging.loan_applications
        WHERE run_id = p_run_id

        UNION

        SELECT reviewed_at::DATE
        FROM staging.loan_applications
        WHERE run_id = p_run_id
          AND reviewed_at IS NOT NULL

        UNION

        SELECT requested_at::DATE
        FROM staging.loans
        WHERE run_id = p_run_id

        UNION

        SELECT due_date
        FROM staging.loan_installments
        WHERE run_id = p_run_id

        UNION

        SELECT paid_at::DATE
        FROM staging.loan_payments
        WHERE run_id = p_run_id
          AND paid_at IS NOT NULL
    )

    SELECT COUNT(*)::INTEGER
    INTO v_date_count
    FROM source_dates
    WHERE full_date IS NOT NULL;


    v_gold_count := v_stage_count + v_date_count;


    ----------------------------------------------------------------
    -- 17. PUBLICAR COMO GOLD CURRENT
    ----------------------------------------------------------------

    UPDATE dataops.published_batches
    SET is_current = FALSE
    WHERE is_current = TRUE;


    INSERT INTO dataops.published_batches (
        batch_id,
        source_run_id,
        publication_status,
        is_current,
        gold_row_count,
        quality_gate_total,
        quality_gate_passed,
        rows_quarantined,
        published_at,
        notes
    )
    VALUES (
        p_run_id,
        p_run_id,
        'PUBLISHED',
        TRUE,
        v_gold_count,
        v_quality_total,
        v_quality_passed,
        v_rows_quarantined,
        NOW(),
        'Gold publicado desde Silver. batch_id = run_id para trazabilidad 1:1 en la PoC.'
    );


    ----------------------------------------------------------------
    -- 18. RESULTADO
    ----------------------------------------------------------------

    RETURN QUERY
    SELECT
        pb.batch_id,
        pb.source_run_id,
        pb.publication_status::TEXT,
        pb.gold_row_count,
        pb.quality_gate_total,
        pb.quality_gate_passed
    FROM dataops.published_batches pb
    WHERE pb.source_run_id = p_run_id;

END;
$$;

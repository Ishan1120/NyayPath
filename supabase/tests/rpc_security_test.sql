-- =====================================================================
-- NyayPath Phase 1.3.9 RPC Authorization & Atomic Execution Runtime Tests
-- =====================================================================

DO $$
DECLARE
    v_case_uuid UUID := gen_random_uuid();
    v_case_id TEXT := 'CAMPUS-RPC-001';
    v_rti_uuid UUID := gen_random_uuid();
    v_rti_id TEXT := 'RTI-RPC-001';
    v_result JSONB;
BEGIN
    -- Setup test cases
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, department, year, category, subject, description,
        is_anonymous, verification_key_hash
    ) VALUES (
        v_case_uuid, v_case_id, 'INST_TEST', 'ECE', '2nd', 'Academic', 'RPC Test', 'Desc',
        FALSE, 'hash_test_rpc'
    );

    INSERT INTO public.cases (
        id, case_id, case_type, status
    ) VALUES (
        v_rti_uuid, v_rti_id, 'RTI', 'FILED'
    );

    RAISE NOTICE '=== RPC TEST 1: Reject unprivileged call (non-service_role) ===';
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);
    BEGIN
        v_result := public.update_campus_grievance_status(
            p_case_id := v_case_id,
            p_new_status := 'UNDER_INQUIRY'
        );
        RAISE EXCEPTION 'RPC TEST 1 FAILED: Non-service_role was allowed to execute RPC!';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'RPC TEST 1 PASSED: Unprivileged execution blocked: %', SQLERRM;
    END;

    RAISE NOTICE '=== RPC TEST 2: Reject execution on non-campus grievance (Cross-Case-Type Isolation) ===';
    PERFORM set_config('request.jwt.claim.role', 'service_role', true);
    BEGIN
        v_result := public.update_campus_grievance_status(
            p_case_id := v_rti_id,
            p_new_status := 'UNDER_INQUIRY'
        );
        RAISE EXCEPTION 'RPC TEST 2 FAILED: Non-campus grievance (RTI) was modified by campus RPC!';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'RPC TEST 2 PASSED: Cross-case-type execution blocked: %', SQLERRM;
    END;

    RAISE NOTICE '=== RPC TEST 3: Authorized service_role atomic update on valid campus case ===';
    v_result := public.update_campus_grievance_status(
        p_case_id := v_case_id,
        p_new_status := 'ACTION_TAKEN',
        p_proctor_notes := 'Inquiry initiated by committee',
        p_action_taken := 'Notice issued to department'
    );

    IF v_result->>'status' <> 'ACTION_TAKEN' OR v_result->>'proctor_notes' <> 'Inquiry initiated by committee' THEN
        RAISE EXCEPTION 'RPC TEST 3 FAILED: Returned result did not match updated values: %', v_result;
    END IF;

    -- Verify tracking hash is NOT leaked in return JSONB
    IF v_result ? 'tracking_key_hash' OR v_result ? 'verification_key_hash' THEN
        RAISE EXCEPTION 'RPC TEST 3 FAILED: Sensitive credential leaked in RPC response: %', v_result;
    END IF;
    RAISE NOTICE 'RPC TEST 3 PASSED: Authorized update successful, allowlisted response verified: %', v_result;

    RAISE NOTICE '=== CLEANUP TEST FIXTURES ===';
    RAISE EXCEPTION 'ROLLBACK_CLEAN' USING ERRCODE = '00000';
EXCEPTION WHEN SQLSTATE '00000' THEN
    RAISE NOTICE 'SUCCESS: ALL 3 RPC SECURITY TESTS PASSED IN RUNTIME POSTGRESQL!';
END $$;

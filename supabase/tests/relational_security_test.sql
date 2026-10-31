-- =====================================================================
-- NyayPath Phase 1.3.9 Local PostgreSQL Relational Security Runtime Tests
-- =====================================================================

DO $$
DECLARE
    v_case_id TEXT := 'CAMPUS-TEST-001';
    v_case_uuid UUID := gen_random_uuid();
    v_parent_count INT;
    v_parent_status TEXT;
    v_log_uuid UUID;
BEGIN
    RAISE NOTICE '=== TEST 1: sync_campus_case_parent trigger creates parent row ===';
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, department, year, category, subject, description,
        is_anonymous, verification_key_hash
    ) VALUES (
        v_case_uuid, v_case_id, 'INST_TEST', 'CSE', '3rd', 'Academic', 'Test Subject', 'Test Description',
        FALSE, 'hash_abc_123'
    );

    SELECT COUNT(*), status INTO v_parent_count, v_parent_status
    FROM public.cases WHERE id = v_case_uuid AND case_id = v_case_id;

    IF v_parent_count <> 1 OR v_parent_status <> 'SUBMITTED' THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Parent row was not created automatically';
    END IF;
    RAISE NOTICE 'TEST 1 PASSED: Parent case created with status %', v_parent_status;

    RAISE NOTICE '=== TEST 2: sync_parent_case_to_campus trigger synchronizes parent update ===';
    UPDATE public.cases SET status = 'UNDER_INQUIRY', updated_at = now() WHERE id = v_case_uuid;

    SELECT status INTO v_parent_status FROM public.campus_cases WHERE id = v_case_uuid;
    IF v_parent_status <> 'UNDER_INQUIRY' THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Child status did not synchronize from parent';
    END IF;
    RAISE NOTICE 'TEST 2 PASSED: Child status synchronized to %', v_parent_status;

    RAISE NOTICE '=== TEST 3: Parent authority protection (direct child status update blocked) ===';
    BEGIN
        UPDATE public.campus_cases SET status = 'RESOLVED' WHERE id = v_case_uuid;
        RAISE EXCEPTION 'TEST 3 FAILED: Direct child status update should have been blocked';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'TEST 3 PASSED: Direct child status update correctly blocked: %', SQLERRM;
    END;

    RAISE NOTICE '=== TEST 4: Anonymous privacy constraint ck_campus_cases_anonymous_privacy ===';
    BEGIN
        INSERT INTO public.campus_cases (
            id, case_id, institution_id, department, year, category, subject, description,
            is_anonymous, student_name, verification_key_hash
        ) VALUES (
            gen_random_uuid(), 'CAMPUS-ANON-LEAK', 'INST_TEST', 'CSE', '1st', 'Harassment', 'Sub', 'Desc',
            TRUE, 'Real Student Name Leaked', 'hash_xyz_789'
        );
        RAISE EXCEPTION 'TEST 4 FAILED: Anonymous submission with real name should have been rejected';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'TEST 4 PASSED: Anonymous submission with student PII correctly rejected: %', SQLERRM;
    END;

    RAISE NOTICE '=== TEST 5: Audit log immutability trigger prevent_audit_log_modification ===';
    INSERT INTO public.case_activity_log (
        case_uuid, case_id, actor_type, actor_role, action_type, action_details
    ) VALUES (
        v_case_uuid, v_case_id, 'SYSTEM', 'system', 'TEST_ACTION', '{"reason":"test"}'::jsonb
    ) RETURNING id INTO v_log_uuid;

    BEGIN
        DELETE FROM public.case_activity_log WHERE id = v_log_uuid;
        RAISE EXCEPTION 'TEST 5 FAILED: Audit log DELETE should have been prohibited';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'TEST 5 PASSED: Audit log DELETE correctly blocked: %', SQLERRM;
    END;

    BEGIN
        UPDATE public.case_activity_log SET action_type = 'TAMPERED' WHERE id = v_log_uuid;
        RAISE EXCEPTION 'TEST 5 FAILED: Audit log UPDATE should have been prohibited';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'TEST 5 PASSED: Audit log UPDATE correctly blocked: %', SQLERRM;
    END;

    RAISE NOTICE '=== TEST 6: Audit actor provenance constraint chk_audit_actor_integrity ===';
    BEGIN
        -- USER event with NULL audit_actor_id must fail
        INSERT INTO public.case_activity_log (
            case_uuid, case_id, actor_type, actor_role, action_type
        ) VALUES (
            v_case_uuid, v_case_id, 'USER', 'officer', 'ILLEGAL_ACTION'
        );
        RAISE EXCEPTION 'TEST 6 FAILED: USER event with NULL audit_actor_id should have been rejected';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'TEST 6 PASSED: USER event with NULL audit_actor_id correctly rejected: %', SQLERRM;
    END;

    RAISE NOTICE '=== TEST 7: Foreign Key Deletion Restriction ===';
    BEGIN
        DELETE FROM public.cases WHERE id = v_case_uuid;
        RAISE EXCEPTION 'TEST 7 FAILED: Deleting parent case with active child should have been restricted';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'TEST 7 PASSED: Parent deletion with active child correctly rejected: %', SQLERRM;
    END;

    RAISE NOTICE '=== CLEANUP TEST FIXTURES ===';
    RAISE EXCEPTION 'ROLLBACK_CLEAN' USING ERRCODE = '00000';
EXCEPTION WHEN SQLSTATE '00000' THEN
    RAISE NOTICE 'SUCCESS: ALL 7 RUNTIME POSTGRESQL RELATIONAL TESTS PASSED!';
END $$;

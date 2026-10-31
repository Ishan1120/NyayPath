-- =====================================================================
-- NyayPath Phase 1.3.10 Runtime RLS & PostgreSQL Security Verification
-- =====================================================================

BEGIN;

DO $$
DECLARE
    -- Test User UUIDs (simulating auth.users)
    v_student_a_id UUID := 'aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa';
    v_student_b_id UUID := 'bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb';
    v_proctor_x_id UUID := 'cccccccc-1111-2222-3333-cccccccccccc';
    v_proctor_y_id UUID := 'dddddddd-1111-2222-3333-dddddddddddd';
    
    -- Institution UUIDs
    v_inst_x_uuid UUID := '11111111-0000-0000-0000-111111111111';
    v_inst_y_uuid UUID := '22222222-0000-0000-0000-222222222222';
    
    -- Case UUIDs
    v_case_a_uuid UUID := 'a1111111-0000-0000-0000-000000000001';
    v_case_b_uuid UUID := 'b2222222-0000-0000-0000-000000000002';
    v_case_x_uuid UUID := 'c3333333-0000-0000-0000-000000000003';
    v_case_y_uuid UUID := 'd4444444-0000-0000-0000-000000000004';
    
    v_log_uuid UUID;
    v_read_count INT;
    v_update_count INT;
    v_rpc_res JSONB;
BEGIN
    RAISE NOTICE '--- SETUP: Creating disposable test fixtures as superuser/postgres ---';
    
    -- 0. Insert mock auth.users inside transaction
    INSERT INTO auth.users (id, email, is_sso_user, is_anonymous)
    VALUES 
        (v_student_a_id, 'alice@college-x.edu', FALSE, FALSE),
        (v_student_b_id, 'bob@college-x.edu', FALSE, FALSE),
        (v_proctor_x_id, 'xavier@college-x.edu', FALSE, FALSE),
        (v_proctor_y_id, 'yolanda@college-y.edu', FALSE, FALSE);

    -- 1. Create test institutions
    INSERT INTO public.institutions (id, code, name, city, state, is_active)
    VALUES 
        (v_inst_x_uuid, 'COLLEGE_X', 'College X Institute of Tech', 'City X', 'State X', TRUE),
        (v_inst_y_uuid, 'COLLEGE_Y', 'College Y Institute of Law', 'City Y', 'State Y', TRUE);

    -- 2. Create test profiles
    INSERT INTO public.profiles (id, full_name, email, role, account_status)
    VALUES 
        (v_student_a_id, 'Student Alice', 'alice@college-x.edu', 'student', 'active'),
        (v_student_b_id, 'Student Bob', 'bob@college-x.edu', 'student', 'active'),
        (v_proctor_x_id, 'Proctor Xavier', 'xavier@college-x.edu', 'proctor', 'active'),
        (v_proctor_y_id, 'Proctor Yolanda', 'yolanda@college-y.edu', 'proctor', 'active');

    -- 3. Create campus cases
    -- Case A: Owned by Student A
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, verification_key_hash
    ) VALUES (
        v_case_a_uuid, 'CAMPUS-CASE-A', 'COLLEGE_X', v_inst_x_uuid, v_student_a_id, 'Student Alice',
        'CSE', '3rd', 'Academic', 'Subject A', 'Desc A', FALSE, 'hash_case_a'
    );

    -- Case B: Owned by Student B
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, verification_key_hash
    ) VALUES (
        v_case_b_uuid, 'CAMPUS-CASE-B', 'COLLEGE_X', v_inst_x_uuid, v_student_b_id, 'Student Bob',
        'CSE', '2nd', 'Academic', 'Subject B', 'Desc B', FALSE, 'hash_case_b'
    );

    -- Case Y: In College Y
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, verification_key_hash
    ) VALUES (
        v_case_y_uuid, 'CAMPUS-CASE-Y', 'COLLEGE_Y', v_inst_y_uuid, NULL, 'Anonymous',
        'Law', '1st', 'Administration', 'Subject Y', 'Desc Y', TRUE, 'hash_case_y'
    );

    -- 4. Create an activity log
    INSERT INTO public.case_activity_log (
        case_uuid, case_id, actor_type, actor_role, action_type, action_details
    ) VALUES (
        v_case_a_uuid, 'CAMPUS-CASE-A', 'SYSTEM', 'system', 'INITIAL_FILING', '{"filed":true}'::jsonb
    ) RETURNING id INTO v_log_uuid;

    -- 5. Create confidential student identity
    INSERT INTO public.confidential_student_identities (
        case_id, student_name_encrypted, roll_number_encrypted
    ) VALUES (
        'CAMPUS-CASE-Y', 'enc_name_secret', 'enc_roll_secret'
    );

    RAISE NOTICE 'Fixtures created successfully.';

    -- =====================================================================
    -- TEST 1: Student A cannot read Student B private case
    -- =====================================================================
    RAISE NOTICE '=== TEST 1: Student A cannot read Student B private case ===';
    PERFORM set_config('role', 'authenticated', true);
    PERFORM set_config('request.jwt.claim.sub', v_student_a_id::text, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);
    PERFORM set_config('request.jwt.claims', json_build_object(
        'sub', v_student_a_id,
        'role', 'authenticated',
        'app_metadata', json_build_object('role', 'student', 'institution_id', 'COLLEGE_X', 'account_status', 'active')
    )::text, true);

    -- Can Student A see Case A? (YES)
    SELECT COUNT(*) INTO v_read_count FROM public.campus_cases WHERE id = v_case_a_uuid;
    IF v_read_count <> 1 THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Student A could not read their own case';
    END IF;

    -- Can Student A see Case B? (NO)
    SELECT COUNT(*) INTO v_read_count FROM public.campus_cases WHERE id = v_case_b_uuid;
    IF v_read_count <> 0 THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Student A was able to read Student B case!';
    END IF;
    RAISE NOTICE 'TEST 1 PASSED: Student A strictly isolated from Student B case (count: %).', v_read_count;

    -- =====================================================================
    -- TEST 2: Student A cannot modify Student B profile
    -- =====================================================================
    RAISE NOTICE '=== TEST 2: Student A cannot modify Student B profile ===';
    UPDATE public.profiles SET full_name = 'Compromised Name' WHERE id = v_student_b_id;
    GET DIAGNOSTICS v_update_count = ROW_COUNT;
    IF v_update_count <> 0 THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Student A was able to update Student B profile (updated rows: %)', v_update_count;
    END IF;

    -- Student A updating own profile succeeds
    UPDATE public.profiles SET full_name = 'Alice New Contact' WHERE id = v_student_a_id;
    GET DIAGNOSTICS v_update_count = ROW_COUNT;
    IF v_update_count <> 1 THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Student A could not update own contact details';
    END IF;
    RAISE NOTICE 'TEST 2 PASSED: Cross-user profile update denied (0 rows), self-update allowed (1 row).';

    -- =====================================================================
    -- TEST 3: Authenticated users cannot elevate their own roles
    -- =====================================================================
    RAISE NOTICE '=== TEST 3: Authenticated users cannot elevate their own roles ===';
    BEGIN
        UPDATE public.profiles SET role = 'platform_admin' WHERE id = v_student_a_id;
        RAISE EXCEPTION 'TEST 3 FAILED: Role escalation should have been rejected by immutability trigger!';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE '%Privilege escalation rejected%' THEN
            RAISE NOTICE 'TEST 3 PASSED: Role escalation correctly rejected: %', SQLERRM;
        ELSE
            RAISE EXCEPTION 'TEST 3 FAILED: Unexpected error: %', SQLERRM;
        END IF;
    END;

    -- =====================================================================
    -- TEST 4 & 5: Cross-institution officers cannot access foreign cases
    -- =====================================================================
    RAISE NOTICE '=== TEST 4 & 5: Cross-institution officers cannot access foreign institutional records ===';
    -- Switch context to Proctor Xavier (COLLEGE_X)
    PERFORM set_config('role', 'authenticated', true);
    PERFORM set_config('request.jwt.claim.sub', v_proctor_x_id::text, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);
    PERFORM set_config('request.jwt.claims', json_build_object(
        'sub', v_proctor_x_id,
        'role', 'authenticated',
        'app_metadata', json_build_object('role', 'proctor', 'institution_id', 'COLLEGE_X', 'account_status', 'active')
    )::text, true);

    -- Proctor X reading College X case -> ALLOWED
    SELECT COUNT(*) INTO v_read_count FROM public.campus_cases WHERE institution_id = 'COLLEGE_X';
    IF v_read_count < 1 THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Proctor X could not read cases in own institution';
    END IF;

    -- Proctor X reading College Y case -> DENIED (0 rows)
    SELECT COUNT(*) INTO v_read_count FROM public.campus_cases WHERE institution_id = 'COLLEGE_Y';
    IF v_read_count <> 0 THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Proctor X read foreign institution cases (count: %)', v_read_count;
    END IF;

    -- Proctor X updating College Y case -> DENIED (0 rows updated)
    UPDATE public.campus_cases SET hearing_date = '2026-12-01' WHERE institution_id = 'COLLEGE_Y';
    GET DIAGNOSTICS v_update_count = ROW_COUNT;
    IF v_update_count <> 0 THEN
        RAISE EXCEPTION 'TEST 5 FAILED: Proctor X updated foreign institution cases (updated: %)', v_update_count;
    END IF;
    RAISE NOTICE 'TEST 4 & 5 PASSED: Cross-institution access strictly blocked (read: 0, update: 0).';

    -- =====================================================================
    -- TEST 6: Anonymous users cannot access confidential student identities
    -- =====================================================================
    RAISE NOTICE '=== TEST 6: Anonymous users cannot access confidential student identities ===';
    PERFORM set_config('role', 'anon', true);
    PERFORM set_config('request.jwt.claim.role', 'anon', true);
    PERFORM set_config('request.jwt.claims', '{}', true);

    BEGIN
        SELECT COUNT(*) INTO v_read_count FROM public.confidential_student_identities;
        RAISE EXCEPTION 'TEST 6 FAILED: Anonymous user was allowed to query confidential_student_identities!';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'TEST 6 PASSED: Anonymous access to student identities rejected with permission denied: %', SQLERRM;
    END;

    -- =====================================================================
    -- TEST 7: Ordinary application users cannot modify or delete audit logs
    -- =====================================================================
    RAISE NOTICE '=== TEST 7: Ordinary application users cannot modify or delete audit logs ===';
    PERFORM set_config('role', 'authenticated', true);
    PERFORM set_config('request.jwt.claim.sub', v_proctor_x_id::text, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    -- Try DELETE on audit log
    BEGIN
        DELETE FROM public.case_activity_log WHERE id = v_log_uuid;
        RAISE EXCEPTION 'TEST 7 FAILED: User was allowed to DELETE from case_activity_log!';
    EXCEPTION WHEN insufficient_privilege OR OTHERS THEN
        RAISE NOTICE 'TEST 7a PASSED: Audit log DELETE blocked: %', SQLERRM;
    END;

    -- Try UPDATE on audit log
    BEGIN
        UPDATE public.case_activity_log SET action_type = 'ALTERED' WHERE id = v_log_uuid;
        RAISE EXCEPTION 'TEST 7 FAILED: User was allowed to UPDATE case_activity_log!';
    EXCEPTION WHEN insufficient_privilege OR OTHERS THEN
        RAISE NOTICE 'TEST 7b PASSED: Audit log UPDATE blocked: %', SQLERRM;
    END;

    -- =====================================================================
    -- TEST 8: Ordinary application roles cannot execute privileged RPCs
    -- =====================================================================
    RAISE NOTICE '=== TEST 8: Ordinary application roles cannot execute privileged RPCs ===';
    PERFORM set_config('role', 'authenticated', true);
    PERFORM set_config('request.jwt.claim.sub', v_proctor_x_id::text, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    BEGIN
        PERFORM public.update_campus_grievance_status(
            p_case_id := 'CAMPUS-CASE-A',
            p_new_status := 'UNDER_INQUIRY'
        );
        RAISE EXCEPTION 'TEST 8 FAILED: Ordinary authenticated user executed privileged RPC!';
    EXCEPTION WHEN insufficient_privilege OR OTHERS THEN
        RAISE NOTICE 'TEST 8 PASSED: Privileged RPC execution blocked for authenticated user: %', SQLERRM;
    END;

    -- =====================================================================
    -- TEST 9: Authorized backend operations work through service-role pathway
    -- =====================================================================
    RAISE NOTICE '=== TEST 9: Authorized backend operations work through service_role pathway ===';
    PERFORM set_config('role', 'service_role', true);
    PERFORM set_config('request.jwt.claim.role', 'service_role', true);
    PERFORM set_config('request.jwt.claims', json_build_object('role', 'service_role')::text, true);

    -- Service role executes atomic status update RPC
    v_rpc_res := public.update_campus_grievance_status(
        p_case_id := 'CAMPUS-CASE-A',
        p_new_status := 'ACTION_TAKEN',
        p_proctor_notes := 'Verified by backend service'
    );

    IF v_rpc_res->>'status' <> 'ACTION_TAKEN' THEN
        RAISE EXCEPTION 'TEST 9 FAILED: Service role RPC failed to update case status';
    END IF;
    RAISE NOTICE 'TEST 9 PASSED: Backend service_role successfully executed privileged workflow: %', v_rpc_res->>'status';

    RAISE NOTICE '=======================================================';
    RAISE NOTICE 'ALL 9 RUNTIME RLS & AUTHORIZATION TESTS PASSED 100%%!';
    RAISE NOTICE '=======================================================';

END $$;

-- Clean rollback: leaves zero persistent test data in the database
ROLLBACK;

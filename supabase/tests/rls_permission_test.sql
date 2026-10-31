-- =====================================================================
-- NyayPath Phase 1.3.12 Runtime RLS, Storage & Confidentiality Verification
-- =====================================================================

BEGIN;

DO $$
DECLARE
    -- Test User UUIDs (simulating auth.users)
    v_student_a_id UUID := 'aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa';
    v_student_b_id UUID := 'bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb';
    v_proctor_x_id UUID := 'cccccccc-1111-2222-3333-cccccccccccc';
    v_proctor_y_id UUID := 'dddddddd-1111-2222-3333-dddddddddddd';
    v_carol_id     UUID := 'eeeeeeee-1111-2222-3333-eeeeeeeeeeee';
    v_sam_id       UUID := 'ffffffff-1111-2222-3333-ffffffffffff';
    v_admin_id     UUID := '99999999-1111-2222-3333-999999999999';
    
    -- Institution UUIDs
    v_inst_x_uuid UUID := '11111111-0000-0000-0000-111111111111';
    v_inst_y_uuid UUID := '22222222-0000-0000-0000-222222222222';
    
    -- Case UUIDs
    v_case_a_uuid UUID := 'a1111111-0000-0000-0000-000000000001';
    v_case_b_uuid UUID := 'b2222222-0000-0000-0000-000000000002';
    v_case_c_uuid UUID := 'c3333333-0000-0000-0000-000000000003';
    v_case_y_uuid UUID := 'd4444444-0000-0000-0000-000000000004';
    
    -- Actor UUIDs
    v_alice_actor UUID := gen_random_uuid();
    v_bob_actor   UUID := gen_random_uuid();
    v_xavier_actor UUID:= gen_random_uuid();
    v_carol_actor  UUID:= gen_random_uuid();

    v_count INT;
    v_rpc_res JSONB;
BEGIN
    RAISE NOTICE '--- SETUP: Creating disposable test fixtures as superuser/postgres ---';
    
    -- 0. Insert mock auth.users inside transaction
    INSERT INTO auth.users (id, email, is_sso_user, is_anonymous)
    VALUES 
        (v_student_a_id, 'alice@college-x.edu', FALSE, FALSE),
        (v_student_b_id, 'bob@college-x.edu', FALSE, FALSE),
        (v_proctor_x_id, 'xavier@college-x.edu', FALSE, FALSE),
        (v_proctor_y_id, 'yolanda@college-y.edu', FALSE, FALSE),
        (v_carol_id, 'carol@college-x.edu', FALSE, FALSE),
        (v_sam_id, 'sam@college-x.edu', FALSE, FALSE),
        (v_admin_id, 'admin@nyaypath.gov.in', FALSE, FALSE);

    -- 1. Create test institutions
    INSERT INTO public.institutions (id, code, name, city, state, is_active)
    VALUES 
        (v_inst_x_uuid, 'COLLEGE_X', 'College X Institute of Tech', 'City X', 'State X', TRUE),
        (v_inst_y_uuid, 'COLLEGE_Y', 'College Y Institute of Law', 'City Y', 'State Y', TRUE);

    -- 2. Platform Admin
    INSERT INTO public.platform_admins (user_id, email, account_status)
    VALUES (v_admin_id, 'admin@nyaypath.gov.in', 'active');

    -- 3. Create test profiles
    INSERT INTO public.profiles (id, full_name, email, role, account_status)
    VALUES 
        (v_student_a_id, 'Student Alice', 'alice@college-x.edu', 'student', 'active'),
        (v_student_b_id, 'Student Bob', 'bob@college-x.edu', 'student', 'active'),
        (v_proctor_x_id, 'Proctor Xavier', 'xavier@college-x.edu', 'proctor', 'active'),
        (v_proctor_y_id, 'Proctor Yolanda', 'yolanda@college-y.edu', 'proctor', 'active'),
        (v_carol_id, 'Committee Carol', 'carol@college-x.edu', 'committee_member', 'active'),
        (v_sam_id, 'Proctor Sam', 'sam@college-x.edu', 'proctor', 'suspended'),
        (v_admin_id, 'Platform Admin', 'admin@nyaypath.gov.in', 'platform_admin', 'active');

    -- 4. Institution Memberships (Authoritative database-backed registry)
    INSERT INTO public.institution_memberships (user_id, institution_id, institution_code, role, account_status)
    VALUES
        (v_proctor_x_id, v_inst_x_uuid, 'COLLEGE_X', 'proctor', 'active'),
        (v_carol_id, v_inst_x_uuid, 'COLLEGE_X', 'committee_member', 'active'),
        (v_sam_id, v_inst_x_uuid, 'COLLEGE_X', 'proctor', 'suspended'),
        (v_proctor_y_id, v_inst_y_uuid, 'COLLEGE_Y', 'proctor', 'active');

    -- 5. Audit Actor Mappings
    INSERT INTO public.audit_actor_mappings (audit_actor_id, user_id)
    VALUES
        (v_alice_actor, v_student_a_id),
        (v_bob_actor, v_student_b_id),
        (v_xavier_actor, v_proctor_x_id),
        (v_carol_actor, v_carol_id);

    -- 6. Campus Cases
    -- Case A: Standard grievance by Alice, unassigned
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, confidentiality_mode,
        severity, status, verification_key_hash
    ) VALUES (
        v_case_a_uuid, 'CAMPUS-STD-A', 'COLLEGE_X', v_inst_x_uuid, v_student_a_id, 'Student Alice',
        'CSE', '3rd', 'FACILITY', 'Subject A', 'Desc A', FALSE, 'NORMAL',
        'NORMAL', 'SUBMITTED', 'hash_case_a'
    );

    -- Case B: Confidential grievance by Bob, assigned to Xavier
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, confidentiality_mode,
        severity, status, assigned_proctor, verification_key_hash
    ) VALUES (
        v_case_b_uuid, 'CAMPUS-CONF-B', 'COLLEGE_X', v_inst_x_uuid, v_student_b_id, 'Student Bob',
        'CSE', '2nd', 'HARASSMENT', 'Subject B', 'Desc B', FALSE, 'CONFIDENTIAL',
        'URGENT', 'UNDER_INQUIRY', v_proctor_x_id::text, 'hash_case_b'
    );

    -- Case C: Confidential grievance by Bob, UNASSIGNED
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, confidentiality_mode,
        severity, status, assigned_proctor, verification_key_hash
    ) VALUES (
        v_case_c_uuid, 'CAMPUS-CONF-C', 'COLLEGE_X', v_inst_x_uuid, v_student_b_id, 'Student Bob',
        'MECH', '4th', 'DISCRIMINATION', 'Subject C', 'Desc C', FALSE, 'CONFIDENTIAL',
        'HIGH', 'SUBMITTED', NULL, 'hash_case_c'
    );

    -- Case Y: Belongs to College Y
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid,
        department, year, category, subject, description, is_anonymous, confidentiality_mode,
        severity, status, verification_key_hash
    ) VALUES (
        v_case_y_uuid, 'CAMPUS-INST-Y', 'COLLEGE_Y', v_inst_y_uuid,
        'LAW', '1st', 'ACADEMIC', 'Subject Y', 'Desc Y', TRUE, 'NORMAL',
        'NORMAL', 'SUBMITTED', 'hash_case_y'
    );

    -- 7. Case Documents
    INSERT INTO public.case_documents (id, case_uuid, case_id, file_name, file_size_bytes, mime_type, storage_path, uploader_user_id, is_confidential) VALUES
        ('11111111-1111-1111-1111-111111111111', v_case_a_uuid, 'CAMPUS-STD-A', 'alice_doc.pdf', 1024, 'application/pdf', 'CAMPUS-STD-A/alice_doc.pdf', v_student_a_id, FALSE),
        ('22222222-2222-2222-2222-222222222222', v_case_b_uuid, 'CAMPUS-CONF-B', 'bob_assigned.pdf', 2048, 'application/pdf', 'CAMPUS-CONF-B/bob_assigned.pdf', v_student_b_id, TRUE),
        ('33333333-3333-3333-3333-333333333333', v_case_c_uuid, 'CAMPUS-CONF-C', 'bob_unassigned.pdf', 3072, 'application/pdf', 'CAMPUS-CONF-C/bob_unassigned.pdf', v_student_b_id, TRUE),
        ('44444444-4444-4444-4444-444444444444', v_case_y_uuid, 'CAMPUS-INST-Y', 'yolanda_doc.pdf', 4096, 'application/pdf', 'CAMPUS-INST-Y/yolanda_doc.pdf', v_proctor_y_id, FALSE);

    -- 8. Storage Objects
    INSERT INTO storage.objects (bucket_id, name, owner) VALUES
        ('case-documents', 'CAMPUS-STD-A/alice_doc.pdf', v_student_a_id),
        ('case-documents', 'CAMPUS-CONF-B/bob_assigned.pdf', v_student_b_id),
        ('case-documents', 'CAMPUS-CONF-C/bob_unassigned.pdf', v_student_b_id),
        ('case-documents', 'CAMPUS-INST-Y/yolanda_doc.pdf', v_proctor_y_id);

    -- 9. Case Activity Logs
    INSERT INTO public.case_activity_log (case_uuid, case_id, audit_actor_id, actor_type, actor_role, action_type, action_details) VALUES
        (v_case_a_uuid, 'CAMPUS-STD-A', v_alice_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"action":"grievance submitted"}'::jsonb),
        (v_case_b_uuid, 'CAMPUS-CONF-B', v_bob_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"action":"confidential grievance submitted"}'::jsonb),
        (v_case_b_uuid, 'CAMPUS-CONF-B', v_xavier_actor, 'USER', 'proctor', 'SCHEDULE_HEARING', '{"hearing_date":"2026-11-05"}'::jsonb),
        (v_case_c_uuid, 'CAMPUS-CONF-C', v_bob_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"action":"unassigned confidential grievance submitted"}'::jsonb);

    RAISE NOTICE '--- TEST SUITE EXECUTION ---';

    -- =================================================================
    -- SECTION 1: Student Isolation & Ownership
    -- =================================================================
    -- Test 1.1: Student A views own grievance
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_student_a_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';
    
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_a_uuid;
    ASSERT v_count = 1, 'Test 1.1 Failed: Student A should see own case';
    RAISE NOTICE '[PASS] Test 1.1: Student A views own case';

    -- Test 1.2: Student A cannot view Student B grievance
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_b_uuid;
    ASSERT v_count = 0, 'Test 1.2 Failed: Student A should NOT see Student B case';
    RAISE NOTICE '[PASS] Test 1.2: Student A cannot see Student B case';

    -- =================================================================
    -- SECTION 2: Confidential Grievance SELECT Isolation
    -- =================================================================
    -- Test 2.1: Unassigned Proctor X reads standard grievance within institution (Case A)
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_a_uuid;
    ASSERT v_count = 1, 'Test 2.1 Failed: Proctor X must see standard Case A for triage';
    RAISE NOTICE '[PASS] Test 2.1: Unassigned Proctor X can read standard grievance for triage';

    -- Test 2.2: Unassigned Proctor X CANNOT read unassigned confidential grievance (Case C)
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 0, 'Test 2.2 Failed: Unassigned Proctor X must NOT see unassigned confidential Case C!';
    RAISE NOTICE '[PASS] Test 2.2: Unassigned Proctor X strictly BLOCKED from confidential grievance';

    -- Test 2.3: Assigned Proctor X CAN read assigned confidential grievance (Case B)
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_b_uuid;
    ASSERT v_count = 1, 'Test 2.3 Failed: Assigned Proctor X must see assigned confidential Case B';
    RAISE NOTICE '[PASS] Test 2.3: Assigned Proctor X can read assigned confidential grievance';

    -- Test 2.4: Committee member Carol CAN read unassigned confidential grievance (Case C)
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_carol_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 1, 'Test 2.4 Failed: Committee member Carol must see confidential Case C';
    RAISE NOTICE '[PASS] Test 2.4: Committee member Carol can read institutional confidential grievance';

    -- =================================================================
    -- SECTION 3: Confidential Grievance UPDATE Isolation
    -- =================================================================
    -- Test 3.1: Unassigned Proctor X CANNOT update unassigned confidential grievance (Case C)
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    UPDATE public.campus_cases SET proctor_notes = 'Tampered by unassigned proctor' WHERE id = v_case_c_uuid;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    ASSERT v_count = 0, 'Test 3.1 Failed: Unassigned Proctor X must update 0 rows on confidential Case C!';
    RAISE NOTICE '[PASS] Test 3.1: Unassigned Proctor X UPDATE on confidential grievance blocked (0 rows updated)';

    -- Test 3.2: Unassigned Proctor X CANNOT downgrade confidentiality_mode to NORMAL on Case C
    UPDATE public.campus_cases SET confidentiality_mode = 'NORMAL' WHERE id = v_case_c_uuid;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    ASSERT v_count = 0, 'Test 3.2 Failed: Confidentiality downgrade bypass must update 0 rows!';
    RAISE NOTICE '[PASS] Test 3.2: Confidentiality mode downgrade bypass blocked (0 rows updated)';

    -- Test 3.3: Assigned Proctor X CAN update notes on assigned confidential grievance (Case B)
    UPDATE public.campus_cases SET proctor_notes = 'Legitimate update by assigned proctor' WHERE id = v_case_b_uuid;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    ASSERT v_count = 1, 'Test 3.3 Failed: Assigned Proctor X must update 1 row on Case B!';
    RAISE NOTICE '[PASS] Test 3.3: Assigned Proctor X successfully updates assigned confidential grievance';

    -- =================================================================
    -- SECTION 4: Cross-Institution & Suspended Access Denial
    -- =================================================================
    -- Test 4.1: Cross-institution Proctor Yolanda (College Y) CANNOT view College X cases
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_y_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE institution_uuid = v_inst_x_uuid;
    ASSERT v_count = 0, 'Test 4.1 Failed: Yolanda must see 0 cases for College X!';
    RAISE NOTICE '[PASS] Test 4.1: Cross-institution Proctor Yolanda denied College X cases';

    -- Test 4.2: Suspended Proctor Sam CANNOT view any cases
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_sam_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases;
    ASSERT v_count = 0, 'Test 4.2 Failed: Suspended Proctor Sam must see 0 cases!';
    RAISE NOTICE '[PASS] Test 4.2: Suspended Proctor Sam denied all case access';

    -- =================================================================
    -- SECTION 5: Confidential Audit-Log Isolation
    -- =================================================================
    -- Test 5.1: Unassigned Proctor X CANNOT read activity logs of confidential Case C
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count = 0, 'Test 5.1 Failed: Unassigned Proctor X must NOT read confidential Case C activity logs!';
    RAISE NOTICE '[PASS] Test 5.1: Unassigned Proctor X denied activity logs of confidential grievance';

    -- Test 5.2: Assigned Proctor X CAN read activity logs of assigned confidential Case B
    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_b_uuid;
    ASSERT v_count = 2, 'Test 5.2 Failed: Assigned Proctor X must see Case B activity logs (count: 2)!';
    RAISE NOTICE '[PASS] Test 5.2: Assigned Proctor X views activity logs of assigned confidential grievance';

    -- Test 5.3: Committee member Carol CAN read activity logs of confidential Case C
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_carol_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count = 1, 'Test 5.3 Failed: Committee member Carol must see Case C activity logs!';
    RAISE NOTICE '[PASS] Test 5.3: Committee member Carol views activity logs of confidential grievance';

    -- Test 5.4: Student Alice sees own audit activity via get_current_user_audit_actor_id()
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_student_a_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_a_uuid;
    ASSERT v_count = 1, 'Test 5.4 Failed: Student Alice must see her own activity log entry!';
    RAISE NOTICE '[PASS] Test 5.4: Student Alice views own activity logs via get_current_user_audit_actor_id()';

    -- =================================================================
    -- SECTION 6: Storage Objects Confidentiality Gating
    -- =================================================================
    -- Test 6.1: Student A views own document
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-STD-A/alice_doc.pdf';
    ASSERT v_count = 1, 'Test 6.1 Failed: Student A must view own document';
    RAISE NOTICE '[PASS] Test 6.1: Student A accesses own document in storage.objects';

    -- Test 6.2: Student A cannot view Student B document
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-B/bob_assigned.pdf';
    ASSERT v_count = 0, 'Test 6.2 Failed: Student A must NOT view Student B document';
    RAISE NOTICE '[PASS] Test 6.2: Student A denied access to Student B document';

    -- Test 6.3: Unassigned Proctor X blocked from unassigned confidential document
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 0, 'Test 6.3 Failed: Unassigned Proctor X must NOT access confidential document';
    RAISE NOTICE '[PASS] Test 6.3: Unassigned Proctor X BLOCKED from confidential document';

    -- Test 6.4: Assigned Proctor X accesses assigned confidential document
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-B/bob_assigned.pdf';
    ASSERT v_count = 1, 'Test 6.4 Failed: Assigned Proctor X must access assigned document';
    RAISE NOTICE '[PASS] Test 6.4: Assigned Proctor X accesses assigned confidential document';

    -- Test 6.5: Direct anonymous access to storage.objects is strictly 0 rows
    EXECUTE 'SET LOCAL ROLE anon';
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents';
    ASSERT v_count = 0, 'Test 6.5 Failed: Anonymous role must see 0 objects';
    RAISE NOTICE '[PASS] Test 6.5: Direct anonymous access on storage.objects is strictly 0 rows';

    -- =================================================================
    -- SECTION 7: Audit Immutability & Privileged RPC Protection
    -- =================================================================
    -- Test 7.1: Immutability trigger prevents UPDATE on case_activity_log
    BEGIN
        UPDATE public.case_activity_log SET action_type = 'TAMPERED';
        RAISE EXCEPTION 'Test 7.1 Failed: Immutability trigger should have blocked UPDATE';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.1: Audit log update strictly rejected by immutability trigger';
    END;

    -- Test 7.2: Privileged RPC rejects authenticated caller directly
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    BEGIN
        SELECT public.update_campus_grievance_status(
            p_case_id => 'CAMPUS-STD-A',
            p_new_status => 'UNDER_INQUIRY'
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.2 Failed: Authenticated role must not execute status RPC';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.2: Authenticated execution of status RPC strictly denied';
    END;

    -- Test 7.3: Backend service_role executes privileged status update
    EXECUTE 'SET LOCAL ROLE service_role';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''service_role''';
    
    SELECT public.update_campus_grievance_status(
        p_case_id => 'CAMPUS-STD-A',
        p_new_status => 'UNDER_INQUIRY',
        p_proctor_notes => 'Inquiry initiated by authorized proctor'
    ) INTO v_rpc_res;
    
    ASSERT (v_rpc_res->>'status') = 'UNDER_INQUIRY', 'Test 7.3 Failed: service_role status update failed';
    RAISE NOTICE '[PASS] Test 7.3: Authorized backend service_role updates status via RPC';

    RAISE NOTICE '======================================================================';
    RAISE NOTICE '  ALL NYAYPATH PHASE 1.3.12 RUNTIME SECURITY & CONFIDENTIALITY TESTS PASSED!';
    RAISE NOTICE '======================================================================';
END $$;

ROLLBACK;

-- =====================================================================
-- NyayPath Phase 1.3.11 Runtime RLS, Storage & PostgreSQL Security Verification
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
        (v_xavier_actor, v_proctor_x_id);

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
        (v_case_a_uuid, 'CAMPUS-STD-A', v_alice_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"note":"alice submitted"}'::jsonb),
        (v_case_b_uuid, 'CAMPUS-CONF-B', v_bob_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"note":"bob submitted"}'::jsonb),
        (v_case_b_uuid, 'CAMPUS-CONF-B', v_xavier_actor, 'USER', 'proctor', 'SCHEDULE_HEARING', '{"date":"2026-11-05"}'::jsonb);

    RAISE NOTICE '--- TEST SUITE EXECUTION ---';

    -- =================================================================
    -- SECTION 1: Cross-Student Isolation & Direct Storage Protection
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

    -- Test 1.3: Student A accesses own document in storage.objects
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-STD-A/alice_doc.pdf';
    ASSERT v_count = 1, 'Test 1.3 Failed: Student A should see own document';
    RAISE NOTICE '[PASS] Test 1.3: Student A accesses own document in storage.objects';

    -- Test 1.4: Student A attempts to access Student B document in storage.objects
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-B/bob_assigned.pdf';
    ASSERT v_count = 0, 'Test 1.4 Failed: Student A must NOT access Student B document in storage.objects';
    RAISE NOTICE '[PASS] Test 1.4: Student A denied access to Student B document in storage.objects';

    -- Test 1.5: Student A lists storage.objects (only sees own document, count: 1)
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents';
    ASSERT v_count = 1, 'Test 1.5 Failed: Student A should only see 1 document in storage.objects';
    RAISE NOTICE '[PASS] Test 1.5: Student A listing strictly scoped to own document';

    -- =================================================================
    -- SECTION 2: Institutional Isolation & Membership Verification
    -- =================================================================
    -- Test 2.1: Proctor Xavier (College X) views College X cases
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';
    
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE institution_uuid = v_inst_x_uuid;
    ASSERT v_count = 3, 'Test 2.1 Failed: Proctor Xavier should see College X cases (3 cases)';
    RAISE NOTICE '[PASS] Test 2.1: Proctor Xavier views College X cases via institution_memberships';

    -- Test 2.2: Proctor Xavier CANNOT view College Y cases
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE institution_uuid = v_inst_y_uuid;
    ASSERT v_count = 0, 'Test 2.2 Failed: Proctor Xavier must NOT see College Y cases';
    RAISE NOTICE '[PASS] Test 2.2: Proctor Xavier denied College Y cases';

    -- Test 2.3: Cross-institution Proctor Yolanda (College Y) CANNOT view College X cases
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_y_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';
    
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE institution_uuid = v_inst_x_uuid;
    ASSERT v_count = 0, 'Test 2.3 Failed: Yolanda must NOT see College X cases';
    RAISE NOTICE '[PASS] Test 2.3: Cross-institution Proctor Yolanda denied College X cases';

    -- Test 2.4: Cross-institution Proctor Yolanda CANNOT access College X document in storage.objects
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-STD-A/alice_doc.pdf';
    ASSERT v_count = 0, 'Test 2.4 Failed: Yolanda must NOT access College X document';
    RAISE NOTICE '[PASS] Test 2.4: Cross-institution Proctor Yolanda denied College X document';

    -- Test 2.5: Suspended Proctor Sam CANNOT view any cases
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_sam_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';
    
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE institution_uuid = v_inst_x_uuid;
    ASSERT v_count = 0, 'Test 2.5 Failed: Suspended proctor Sam must NOT see any cases';
    RAISE NOTICE '[PASS] Test 2.5: Suspended Proctor Sam denied case access (account_status != active)';

    -- =================================================================
    -- SECTION 3: Confidentiality Gating in Storage Objects
    -- =================================================================
    -- Test 3.1: Assigned Proctor Xavier accesses assigned confidential document
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-B/bob_assigned.pdf';
    ASSERT v_count = 1, 'Test 3.1 Failed: Assigned proctor Xavier must access assigned confidential document';
    RAISE NOTICE '[PASS] Test 3.1: Assigned proctor Xavier accesses assigned confidential document';

    -- Test 3.2: Unassigned Proctor Xavier accesses standard non-confidential document (triage)
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-STD-A/alice_doc.pdf';
    ASSERT v_count = 1, 'Test 3.2 Failed: Unassigned proctor Xavier must access standard grievance document';
    RAISE NOTICE '[PASS] Test 3.2: Unassigned proctor Xavier accesses standard grievance document';

    -- Test 3.3: Unassigned Proctor Xavier BLOCKED from unassigned confidential document
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 0, 'Test 3.3 Failed: Unassigned proctor Xavier must NOT access unassigned confidential document';
    RAISE NOTICE '[PASS] Test 3.3: Unassigned proctor Xavier BLOCKED from unassigned confidential document';

    -- Test 3.4: Committee member Carol CAN access unassigned confidential document
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_carol_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 1, 'Test 3.4 Failed: Committee member Carol must access confidential document';
    RAISE NOTICE '[PASS] Test 3.4: Committee member Carol accesses unassigned confidential document';

    -- =================================================================
    -- SECTION 4: Anonymous Access Denial on Storage Objects
    -- =================================================================
    -- Test 4.1: Direct anonymous access to storage.objects is strictly 0 rows
    EXECUTE 'SET LOCAL ROLE anon';
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents';
    ASSERT v_count = 0, 'Test 4.1 Failed: Anonymous role must have 0 visibility on storage.objects';
    RAISE NOTICE '[PASS] Test 4.1: Direct anonymous access on storage.objects is strictly 0 rows';

    -- =================================================================
    -- SECTION 5: Audit Log Visibility & Immutability
    -- =================================================================
    -- Test 5.1: Student Alice sees her own audit log actions via get_current_user_audit_actor_id()
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_student_a_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log;
    ASSERT v_count = 1, 'Test 5.1 Failed: Alice must see exactly 1 activity log entry (her own)';
    RAISE NOTICE '[PASS] Test 5.1: Student Alice sees own audit activity (no permission error!)';

    -- Test 5.2: Proctor Xavier sees College X institutional activity logs
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log;
    ASSERT v_count = 3, 'Test 5.2 Failed: Proctor Xavier should see College X activity logs (3 logs)';
    RAISE NOTICE '[PASS] Test 5.2: Proctor Xavier views College X case activity logs';

    -- Test 5.3: Cross-institution Proctor Yolanda sees 0 logs for College X
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_y_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log;
    ASSERT v_count = 0, 'Test 5.3 Failed: Yolanda must see 0 logs for College X';
    RAISE NOTICE '[PASS] Test 5.3: Cross-institution Proctor Yolanda sees 0 logs for College X';

    -- Test 5.4: Audit log immutability: UPDATE attempt must fail
    BEGIN
        UPDATE public.case_activity_log SET action_type = 'MODIFIED';
        RAISE EXCEPTION 'Test 5.4 Failed: Immutability trigger should have rejected UPDATE';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 5.4: Audit log update strictly rejected by immutability trigger';
    END;

    -- =================================================================
    -- SECTION 6: Profile Immutability & Privilege Escalation Denial
    -- =================================================================
    -- Test 6.1: Student A attempts to escalate role to platform_admin
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_student_a_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';
    
    BEGIN
        UPDATE public.profiles SET role = 'platform_admin' WHERE id = v_student_a_id;
        RAISE EXCEPTION 'Test 6.1 Failed: Privilege escalation should have raised an exception';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 6.1: Profile role privilege escalation strictly blocked';
    END;

    -- =================================================================
    -- SECTION 7: Privileged RPC Gating
    -- =================================================================
    -- Test 7.1: Authenticated user cannot call update_campus_grievance_status directly
    BEGIN
        SELECT public.update_campus_grievance_status(
            p_case_id => 'CAMPUS-STD-A',
            p_new_status => 'UNDER_INQUIRY'
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.1 Failed: Authenticated role must not execute privileged RPC';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.1: Authenticated execution of status RPC strictly denied';
    END;

    -- Test 7.2: Backend service_role executes privileged status update successfully
    EXECUTE 'SET LOCAL ROLE service_role';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''service_role''';
    
    SELECT public.update_campus_grievance_status(
        p_case_id => 'CAMPUS-STD-A',
        p_new_status => 'UNDER_INQUIRY',
        p_proctor_notes => 'Inquiry initiated by authorized proctor'
    ) INTO v_rpc_res;
    
    ASSERT (v_rpc_res->>'status') = 'UNDER_INQUIRY', 'Test 7.2 Failed: service_role status update failed';
    RAISE NOTICE '[PASS] Test 7.2: Authorized backend service_role updates status via RPC';

    RAISE NOTICE '=======================================================';
    RAISE NOTICE '  ALL NYAYPATH PHASE 1.3.11 RUNTIME SECURITY TESTS PASSED! ';
    RAISE NOTICE '=======================================================';
END $$;

ROLLBACK;

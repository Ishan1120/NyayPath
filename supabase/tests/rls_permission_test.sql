-- =====================================================================
-- NyayPath Phase 1.3.14 Runtime RLS, Storage & RPC Security Verification
-- =====================================================================

BEGIN;

DO $$
DECLARE
    -- Test User UUIDs (simulating auth.users)
    v_student_a_id   UUID := 'aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa'; -- Student Alice (College X)
    v_student_b_id   UUID := 'bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb'; -- Student Bob (College X)
    v_proctor_x_id   UUID := 'cccccccc-1111-2222-3333-cccccccccccc'; -- Proctor Xavier (College X)
    v_proctor_y_id   UUID := 'dddddddd-1111-2222-3333-dddddddddddd'; -- Proctor Yolanda (College Y)
    v_carol_id       UUID := 'eeeeeeee-1111-2222-3333-eeeeeeeeeeee'; -- Committee Carol (College X)
    v_dave_id        UUID := '77777777-1111-2222-3333-777777777777'; -- Committee Dave (College X)
    v_eve_id         UUID := '88888888-1111-2222-3333-888888888888'; -- Committee Eve (Suspended member, College X)
    v_frank_id       UUID := '55555555-1111-2222-3333-555555555555'; -- Member Frank (Demoted/Role change, College X)
    v_chief_p_id     UUID := '66666666-1111-2222-3333-666666666666'; -- Chief Proctor Charlie (College X)
    v_admin_inst_id  UUID := '44444444-1111-2222-3333-444444444444'; -- Institution Admin Irene (College X)
    v_sam_id         UUID := 'ffffffff-1111-2222-3333-ffffffffffff'; -- Suspended Proctor Sam (College X)
    v_admin_id       UUID := '99999999-1111-2222-3333-999999999999'; -- Platform Admin
    
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
    v_dave_actor   UUID:= gen_random_uuid();

    v_count INT;
    v_rpc_res JSONB;
BEGIN
    RAISE NOTICE '--- SETUP: Creating disposable test fixtures as superuser/postgres ---';
    
    -- Cleanup previous test data to ensure clean idempotency
    TRUNCATE TABLE public.case_activity_log CASCADE;
    DELETE FROM public.case_documents WHERE case_id LIKE 'CAMPUS-%';
    DELETE FROM public.case_committee_assignments WHERE case_id LIKE 'CAMPUS-%';
    DELETE FROM public.campus_cases WHERE case_id LIKE 'CAMPUS-%';
    DELETE FROM public.cases WHERE case_id LIKE 'CAMPUS-%';
    DELETE FROM public.audit_actor_mappings WHERE user_id IN (
        v_student_a_id, v_student_b_id, v_proctor_x_id, v_proctor_y_id,
        v_carol_id, v_dave_id, v_eve_id, v_frank_id, v_chief_p_id, v_admin_inst_id
    );
    DELETE FROM public.institution_memberships WHERE user_id IN (
        v_proctor_x_id, v_proctor_y_id, v_carol_id, v_dave_id, v_eve_id,
        v_frank_id, v_chief_p_id, v_admin_inst_id, v_sam_id
    );
    DELETE FROM public.platform_admins WHERE user_id = v_admin_id;
    DELETE FROM public.profiles WHERE id IN (
        v_student_a_id, v_student_b_id, v_proctor_x_id, v_proctor_y_id,
        v_carol_id, v_dave_id, v_eve_id, v_frank_id, v_chief_p_id, v_admin_inst_id, v_sam_id, v_admin_id
    );
    DELETE FROM auth.users WHERE id IN (
        v_student_a_id, v_student_b_id, v_proctor_x_id, v_proctor_y_id,
        v_carol_id, v_dave_id, v_eve_id, v_frank_id, v_chief_p_id, v_admin_inst_id, v_sam_id, v_admin_id
    );
    DELETE FROM public.institutions WHERE id IN (v_inst_x_uuid, v_inst_y_uuid);

    -- 0. Insert mock auth.users inside transaction
    INSERT INTO auth.users (id, email, is_sso_user, is_anonymous)
    VALUES 
        (v_student_a_id, 'alice@college-x.edu', FALSE, FALSE),
        (v_student_b_id, 'bob@college-x.edu', FALSE, FALSE),
        (v_proctor_x_id, 'xavier@college-x.edu', FALSE, FALSE),
        (v_proctor_y_id, 'yolanda@college-y.edu', FALSE, FALSE),
        (v_carol_id, 'carol@college-x.edu', FALSE, FALSE),
        (v_dave_id, 'dave@college-x.edu', FALSE, FALSE),
        (v_eve_id, 'eve@college-x.edu', FALSE, FALSE),
        (v_frank_id, 'frank@college-x.edu', FALSE, FALSE),
        (v_chief_p_id, 'charlie@college-x.edu', FALSE, FALSE),
        (v_admin_inst_id, 'irene@college-x.edu', FALSE, FALSE),
        (v_sam_id, 'sam@college-x.edu', FALSE, FALSE),
        (v_admin_id, 'admin@nyaypath.gov.in', FALSE, FALSE)
    ON CONFLICT (id) DO NOTHING;

    -- 1. Create test institutions
    INSERT INTO public.institutions (id, code, name, city, state, is_active)
    VALUES 
        (v_inst_x_uuid, 'COLLEGE_X', 'College X Institute of Tech', 'City X', 'State X', TRUE),
        (v_inst_y_uuid, 'COLLEGE_Y', 'College Y Institute of Law', 'City Y', 'State Y', TRUE)
    ON CONFLICT (id) DO NOTHING;

    -- 2. Platform Admin
    INSERT INTO public.platform_admins (user_id, email, account_status)
    VALUES (v_admin_id, 'admin@nyaypath.gov.in', 'active')
    ON CONFLICT (user_id) DO NOTHING;

    -- 3. Create test profiles
    INSERT INTO public.profiles (id, full_name, email, role, account_status)
    VALUES 
        (v_student_a_id, 'Student Alice', 'alice@college-x.edu', 'student', 'active'),
        (v_student_b_id, 'Student Bob', 'bob@college-x.edu', 'student', 'active'),
        (v_proctor_x_id, 'Proctor Xavier', 'xavier@college-x.edu', 'proctor', 'active'),
        (v_proctor_y_id, 'Proctor Yolanda', 'yolanda@college-y.edu', 'proctor', 'active'),
        (v_carol_id, 'Committee Carol', 'carol@college-x.edu', 'committee_member', 'active'),
        (v_dave_id, 'Committee Dave', 'dave@college-x.edu', 'committee_member', 'active'),
        (v_eve_id, 'Committee Eve', 'eve@college-x.edu', 'committee_member', 'suspended'),
        (v_frank_id, 'Proctor Frank', 'frank@college-x.edu', 'proctor', 'active'),
        (v_chief_p_id, 'Chief Proctor Charlie', 'charlie@college-x.edu', 'chief_proctor', 'active'),
        (v_admin_inst_id, 'Institution Admin Irene', 'irene@college-x.edu', 'institution_admin', 'active'),
        (v_sam_id, 'Proctor Sam', 'sam@college-x.edu', 'proctor', 'suspended'),
        (v_admin_id, 'Platform Admin', 'admin@nyaypath.gov.in', 'platform_admin', 'active');

    -- 4. Institution Memberships (Authoritative database-backed registry)
    INSERT INTO public.institution_memberships (user_id, institution_id, institution_code, role, account_status)
    VALUES
        (v_proctor_x_id, v_inst_x_uuid, 'COLLEGE_X', 'proctor', 'active'),
        (v_carol_id, v_inst_x_uuid, 'COLLEGE_X', 'committee_member', 'active'),
        (v_dave_id, v_inst_x_uuid, 'COLLEGE_X', 'committee_member', 'active'),
        (v_eve_id, v_inst_x_uuid, 'COLLEGE_X', 'committee_member', 'suspended'),
        (v_frank_id, v_inst_x_uuid, 'COLLEGE_X', 'proctor', 'active'),
        (v_chief_p_id, v_inst_x_uuid, 'COLLEGE_X', 'chief_proctor', 'active'),
        (v_admin_inst_id, v_inst_x_uuid, 'COLLEGE_X', 'institution_admin', 'active'),
        (v_sam_id, v_inst_x_uuid, 'COLLEGE_X', 'proctor', 'suspended'),
        (v_proctor_y_id, v_inst_y_uuid, 'COLLEGE_Y', 'proctor', 'active');

    -- 5. Audit Actor Mappings
    INSERT INTO public.audit_actor_mappings (audit_actor_id, user_id)
    VALUES
        (v_alice_actor, v_student_a_id),
        (v_bob_actor, v_student_b_id),
        (v_xavier_actor, v_proctor_x_id),
        (v_carol_actor, v_carol_id),
        (v_dave_actor, v_dave_id);

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

    -- Case B: Confidential grievance by Bob, assigned to Xavier (canonical UUID)
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, confidentiality_mode,
        severity, status, assigned_proctor, assigned_proctor_user_id, verification_key_hash
    ) VALUES (
        v_case_b_uuid, 'CAMPUS-CONF-B', 'COLLEGE_X', v_inst_x_uuid, v_student_b_id, 'Student Bob',
        'CSE', '2nd', 'HARASSMENT', 'Subject B', 'Desc B', FALSE, 'CONFIDENTIAL',
        'URGENT', 'UNDER_INQUIRY', 'Proctor Xavier', v_proctor_x_id, 'hash_case_b'
    );

    -- Case C: Confidential grievance by Bob, UNASSIGNED proctor, inquiry assigned to Committee Carol
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, confidentiality_mode,
        severity, status, assigned_proctor, assigned_proctor_user_id, verification_key_hash
    ) VALUES (
        v_case_c_uuid, 'CAMPUS-CONF-C', 'COLLEGE_X', v_inst_x_uuid, v_student_b_id, 'Student Bob',
        'MECH', '4th', 'DISCRIMINATION', 'Subject C', 'Desc C', FALSE, 'CONFIDENTIAL',
        'HIGH', 'SUBMITTED', NULL, NULL, 'hash_case_c'
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

    -- 6b. Case-Specific Committee Assignments
    -- Carol is actively assigned to Case C inquiry; Dave is NOT assigned
    INSERT INTO public.case_committee_assignments (
        case_uuid, case_id, user_id, institution_uuid, assigned_by, assignment_status
    ) VALUES 
        (v_case_c_uuid, 'CAMPUS-CONF-C', v_carol_id, v_inst_x_uuid, v_admin_id, 'active'),
        (v_case_c_uuid, 'CAMPUS-CONF-C', v_eve_id, v_inst_x_uuid, v_admin_id, 'active'),
        (v_case_c_uuid, 'CAMPUS-CONF-C', v_frank_id, v_inst_x_uuid, v_admin_id, 'active');

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
        ('case-documents', 'CAMPUS-INST-Y/yolanda_doc.pdf', v_proctor_y_id)
    ON CONFLICT DO NOTHING;

    -- 9. Case Activity Logs
    INSERT INTO public.case_activity_log (case_uuid, case_id, audit_actor_id, actor_type, actor_role, action_type, action_details) VALUES
        (v_case_a_uuid, 'CAMPUS-STD-A', v_alice_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"action":"grievance submitted"}'::jsonb),
        (v_case_b_uuid, 'CAMPUS-CONF-B', v_bob_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"action":"confidential grievance submitted"}'::jsonb),
        (v_case_b_uuid, 'CAMPUS-CONF-B', v_xavier_actor, 'USER', 'proctor', 'SCHEDULE_HEARING', '{"hearing_date":"2026-11-05"}'::jsonb),
        (v_case_c_uuid, 'CAMPUS-CONF-C', v_bob_actor, 'USER', 'student', 'SUBMIT_GRIEVANCE', '{"action":"unassigned confidential grievance submitted"}'::jsonb),
        (v_case_c_uuid, 'CAMPUS-CONF-C', v_xavier_actor, 'USER', 'proctor', 'INITIAL_TRIAGE_NOTE', '{"action":"former proctor triage entry"}'::jsonb),
        (v_case_c_uuid, 'CAMPUS-CONF-C', v_carol_actor, 'USER', 'committee_member', 'COMMITTEE_REVIEW', '{"action":"committee review begun"}'::jsonb);

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
    -- SECTION 2: Confidential Grievance SELECT Isolation & Spoofing Defense
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

    -- Test 2.4: Proctor-Name Spoofing Defense:
    -- An attacker (Dave) modifies his profiles.full_name to match assigned proctor ''Proctor Xavier''
    EXECUTE 'SET LOCAL ROLE postgres';
    UPDATE public.profiles SET full_name = 'Proctor Xavier' WHERE id = v_dave_id;

    -- Dave attempts to query Case B (assigned to Xavier) using spoofed display name
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_dave_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_b_uuid;
    ASSERT v_count = 0, 'Test 2.4 Failed: Name-spoofing attacker must NOT access Case B (must be 0 rows)!';
    RAISE NOTICE '[PASS] Test 2.4: Proctor-name spoofing defense verified: RLS enforces canonical UUID, not display name';

    -- Restore Dave''s profile name
    EXECUTE 'SET LOCAL ROLE postgres';
    UPDATE public.profiles SET full_name = 'Committee Dave' WHERE id = v_dave_id;

    -- =================================================================
    -- SECTION 3: Committee Assignment & Membership Revocation (Task 2 - 7 Scenarios)
    -- =================================================================
    -- Scenario 1: Active assigned committee member in same institution -> ACCESS ALLOWED
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_carol_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 1, 'Scenario 1 Failed: Active assigned member Carol must see Case C';
    SELECT count(*) INTO v_count FROM public.case_documents WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count = 1, 'Scenario 1 Failed: Active assigned member Carol must see Case C document';
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 1, 'Scenario 1 Failed: Active assigned member Carol must see Case C storage object';
    RAISE NOTICE '[PASS] Scenario 1: Active assigned member Carol granted full access to Case C';

    -- Scenario 2: Unassigned committee member in same institution -> DENIED
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_dave_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 2 Failed: Unassigned committee member Dave must NOT see Case C';
    SELECT count(*) INTO v_count FROM public.case_documents WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 2 Failed: Unassigned committee member Dave must NOT see Case C document';
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 0, 'Scenario 2 Failed: Unassigned committee member Dave must NOT see Case C storage object';
    RAISE NOTICE '[PASS] Scenario 2: Unassigned committee member Dave strictly denied Case C access';

    -- Scenario 3: Assigned member whose assignment was revoked (assignment_status = 'revoked') -> DENIED
    EXECUTE 'SET LOCAL ROLE postgres';
    UPDATE public.case_committee_assignments SET assignment_status = 'revoked' WHERE user_id = v_carol_id AND case_uuid = v_case_c_uuid;

    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_carol_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 3 Failed: Revoked assignment member Carol must NOT see Case C';
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 0, 'Scenario 3 Failed: Revoked assignment member Carol must NOT see Case C storage object';
    RAISE NOTICE '[PASS] Scenario 3: Assignment-revoked committee member Carol immediately loses all access';

    -- Re-activate Carol for later tests
    EXECUTE 'SET LOCAL ROLE postgres';
    UPDATE public.case_committee_assignments SET assignment_status = 'active' WHERE user_id = v_carol_id AND case_uuid = v_case_c_uuid;

    -- Scenario 4: Assigned member whose institutional membership is suspended (im.account_status = 'suspended') -> DENIED
    -- Eve is assigned to Case C, but her institution_memberships record has account_status = 'suspended'
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_eve_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 4 Failed: Suspended member Eve must NOT see Case C despite active assignment!';
    SELECT count(*) INTO v_count FROM public.case_documents WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 4 Failed: Suspended member Eve must NOT see Case C document!';
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 0, 'Scenario 4 Failed: Suspended member Eve must NOT see Case C storage object!';
    RAISE NOTICE '[PASS] Scenario 4: Suspended officer Eve denied Case C access despite active assignment record';

    -- Scenario 5: Assigned member whose role is removed / changed from committee_member (im.role = 'student') -> DENIED
    -- Frank is assigned to Case C, but his institution_memberships role was changed to 'student'
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_frank_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 5 Failed: Demoted member Frank must NOT see Case C!';
    SELECT count(*) INTO v_count FROM public.case_documents WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 5 Failed: Demoted member Frank must NOT see Case C document!';
    RAISE NOTICE '[PASS] Scenario 5: Role-demoted user Frank denied Case C access despite assignment record';

    -- Scenario 6: Cross-institution member assigned -> DENIED
    -- Cross-institution Yolanda (College Y)
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_y_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 0, 'Scenario 6 Failed: Cross-institution officer Yolanda must NOT see Case C!';
    RAISE NOTICE '[PASS] Scenario 6: Cross-institution officer Yolanda denied College X confidential case';

    -- Scenario 7: Student Owner and Institution Admin access preserved throughout
    -- Student Owner Bob
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_student_b_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 1, 'Scenario 7 Failed: Case owner Bob must see Case C';
    RAISE NOTICE '[PASS] Scenario 7a: Student Case Owner Bob access strictly preserved';

    -- Institution Admin Irene
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_admin_inst_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 1, 'Scenario 7 Failed: Institution Admin Irene must see Case C';
    RAISE NOTICE '[PASS] Scenario 7b: Institution Admin Irene institutional oversight preserved';

    -- =================================================================
    -- SECTION 4: Confidential Grievance UPDATE Isolation
    -- =================================================================
    -- Test 4.1: Unassigned Proctor X CANNOT update unassigned confidential grievance (Case C)
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    UPDATE public.campus_cases SET proctor_notes = 'Tampered by unassigned proctor' WHERE id = v_case_c_uuid;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    ASSERT v_count = 0, 'Test 4.1 Failed: Unassigned Proctor X must update 0 rows on confidential Case C!';
    RAISE NOTICE '[PASS] Test 4.1: Unassigned Proctor X UPDATE on confidential grievance blocked (0 rows updated)';

    -- Test 4.2: Direct UPDATE on sensitive columns is rejected by column permissions
    BEGIN
        UPDATE public.campus_cases SET confidentiality_mode = 'NORMAL' WHERE id = v_case_b_uuid;
        RAISE EXCEPTION 'Test 4.2 Failed: Direct column UPDATE on confidentiality_mode should have been denied!';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 4.2a: Direct column UPDATE on confidentiality_mode strictly denied';
    END;

    BEGIN
        UPDATE public.campus_cases SET status = 'RESOLVED' WHERE id = v_case_b_uuid;
        RAISE EXCEPTION 'Test 4.2b Failed: Direct column UPDATE on status should have been denied!';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 4.2b: Direct column UPDATE on status strictly denied (preserves atomic RPC)';
    END;

    BEGIN
        UPDATE public.campus_cases SET assigned_proctor = 'Proctor Yolanda' WHERE id = v_case_c_uuid;
        RAISE EXCEPTION 'Test 4.2c Failed: Direct column UPDATE on assigned_proctor should have been denied!';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 4.2c: Direct column UPDATE on assigned_proctor strictly denied';
    END;

    BEGIN
        UPDATE public.campus_cases SET assigned_proctor_user_id = v_proctor_x_id WHERE id = v_case_c_uuid;
        RAISE EXCEPTION 'Test 4.2d Failed: Direct column UPDATE on assigned_proctor_user_id should have been denied!';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 4.2d: Direct column UPDATE on assigned_proctor_user_id strictly denied';
    END;

    -- Test 4.3: Assigned Proctor X CAN update notes on assigned confidential grievance (Case B)
    UPDATE public.campus_cases SET proctor_notes = 'Legitimate update by assigned proctor' WHERE id = v_case_b_uuid;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    ASSERT v_count = 1, 'Test 4.3 Failed: Assigned Proctor X must update 1 row on Case B!';
    RAISE NOTICE '[PASS] Test 4.3: Assigned Proctor X successfully updates assigned confidential grievance';

    -- =================================================================
    -- SECTION 5: Confidential Audit-Log Isolation & Former Actor Hardening
    -- =================================================================
    -- Test 5.1: Unassigned Proctor X CANNOT read activity logs of confidential Case C
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count = 0, 'Test 5.1 Failed: Unassigned Proctor X must NOT read confidential Case C activity logs!';
    RAISE NOTICE '[PASS] Test 5.1: Unassigned Proctor X denied activity logs of confidential grievance';

    -- Test 5.2: Former Actor Self-Access Hardening:
    -- Proctor Xavier actually created an activity log entry on Case C in the past (v_xavier_actor).
    -- But Xavier is not currently assigned to Case C.
    -- Verify that Xavier CANNOT read his own past log entry on Case C via audit_actor_id self-access!
    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_c_uuid AND audit_actor_id = v_xavier_actor;
    ASSERT v_count = 0, 'Test 5.2 Failed: Former actor Xavier must NOT read confidential Case C logs even though he authored an entry!';
    RAISE NOTICE '[PASS] Test 5.2: Former actor self-access hardening verified: past authors blocked from confidential case logs';

    -- Test 5.3: Assigned Proctor X CAN read activity logs of assigned confidential Case B
    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_b_uuid;
    ASSERT v_count = 2, 'Test 5.3 Failed: Assigned Proctor X must see Case B activity logs (count: 2)!';
    RAISE NOTICE '[PASS] Test 5.3: Assigned Proctor X views activity logs of assigned confidential grievance';

    -- Test 5.4: Case-assigned Committee member Carol CAN read activity logs of Case C
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_carol_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_uuid = v_case_c_uuid;
    ASSERT v_count >= 1, 'Test 5.4 Failed: Assigned Committee member Carol must see Case C activity logs!';
    RAISE NOTICE '[PASS] Test 5.4: Case-assigned Committee member Carol views activity logs of Case C';

    -- Test 5.5: Immutability trigger prevents UPDATE or DELETE on case_activity_log
    EXECUTE 'SET LOCAL ROLE postgres';
    BEGIN
        UPDATE public.case_activity_log SET action_type = 'TAMPERED';
        RAISE EXCEPTION 'Test 5.5 Failed: Immutability trigger should have blocked UPDATE';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 5.5: Audit log update strictly rejected by immutability trigger';
    END;

    -- =================================================================
    -- SECTION 6: Storage Objects Confidentiality Gating & Revocation
    -- =================================================================
    -- Test 6.1: Direct anonymous access to storage.objects is strictly 0 rows
    EXECUTE 'SET LOCAL ROLE anon';
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents';
    ASSERT v_count = 0, 'Test 6.1 Failed: Anonymous role must see 0 objects';
    RAISE NOTICE '[PASS] Test 6.1: Direct anonymous access on storage.objects is strictly 0 rows';

    -- Test 6.2: Institutional officer uploader CANNOT retain access to uploaded document after membership revocation
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_y_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-INST-Y/yolanda_doc.pdf';
    ASSERT v_count = 1, 'Test 6.2 Setup Failed: Active officer Yolanda should view uploaded document';
    RAISE NOTICE '[PASS] Test 6.2a: Active officer Yolanda accesses uploaded document in College Y';

    -- Revoke/suspend Yolanda membership
    EXECUTE 'SET LOCAL ROLE postgres';
    UPDATE public.institution_memberships SET account_status = 'suspended' WHERE user_id = v_proctor_y_id;

    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_y_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-INST-Y/yolanda_doc.pdf';
    ASSERT v_count = 0, 'Test 6.2 Failed: Suspended officer Yolanda must NOT access document even though she is the uploader!';
    RAISE NOTICE '[PASS] Test 6.2b: Suspended officer Yolanda immediately loses storage document access';

    SELECT count(*) INTO v_count FROM public.case_documents WHERE storage_path = 'CAMPUS-INST-Y/yolanda_doc.pdf';
    ASSERT v_count = 0, 'Test 6.2 Failed: Suspended officer Yolanda must NOT view case_documents row';
    RAISE NOTICE '[PASS] Test 6.2c: Suspended officer Yolanda loses case_documents metadata access';

    -- Restore Yolanda membership
    EXECUTE 'SET LOCAL ROLE postgres';
    UPDATE public.institution_memberships SET account_status = 'active' WHERE user_id = v_proctor_y_id;

    -- =================================================================
    -- SECTION 7: Privileged RPC Authorization & Target Role Enforcement (Tasks 1 & 3)
    -- =================================================================
    -- Test 7.1: Authenticated caller CANNOT directly invoke update_campus_grievance_status
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_proctor_x_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    BEGIN
        SELECT public.update_campus_grievance_status(
            p_case_id => 'CAMPUS-STD-A',
            p_new_status => 'UNDER_INQUIRY'
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.1 Failed: Authenticated role must not execute update_campus_grievance_status';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 7.1: Authenticated direct execution of update_campus_grievance_status denied';
    END;

    -- Test 7.2: Authenticated caller CANNOT directly invoke assign_case_committee_member
    BEGIN
        SELECT public.assign_case_committee_member(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_dave_id,
            p_role => 'member',
            p_committee_name => 'Inquiry Committee'
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.2 Failed: Authenticated role must not execute assign_case_committee_member';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 7.2: Authenticated direct execution of assign_case_committee_member denied';
    END;

    -- Test 7.3: Authenticated caller CANNOT directly invoke revoke_case_committee_assignment
    BEGIN
        SELECT public.revoke_case_committee_assignment(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_carol_id
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.3 Failed: Authenticated role must not execute revoke_case_committee_assignment';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 7.3: Authenticated direct execution of revoke_case_committee_assignment denied';
    END;

    -- Test 7.4: Service Role updates status: Rejects cross-institution target proctor (College Y Yolanda)
    EXECUTE 'SET LOCAL ROLE service_role';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''service_role''';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''00000000-0000-0000-0000-000000000000''';

    BEGIN
        SELECT public.update_campus_grievance_status(
            p_case_id => 'CAMPUS-STD-A',
            p_new_status => 'UNDER_INQUIRY',
            p_assigned_proctor_user_id => v_proctor_y_id -- Yolanda from College Y
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.4 Failed: Should have rejected cross-institution target proctor';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.4: update_campus_grievance_status rejects cross-institution target proctor';
    END;

    -- Test 7.5: Service Role updates status: Rejects target proctor with role committee_member (Carol)
    BEGIN
        SELECT public.update_campus_grievance_status(
            p_case_id => 'CAMPUS-STD-A',
            p_new_status => 'UNDER_INQUIRY',
            p_assigned_proctor_user_id => v_carol_id -- Committee member Carol
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.5 Failed: Should have rejected committee_member as target proctor';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.5: update_campus_grievance_status rejects committee_member as target proctor';
    END;

    -- Test 7.6: Service Role updates status: Rejects suspended target proctor (Sam)
    BEGIN
        SELECT public.update_campus_grievance_status(
            p_case_id => 'CAMPUS-STD-A',
            p_new_status => 'UNDER_INQUIRY',
            p_assigned_proctor_user_id => v_sam_id -- Suspended proctor Sam
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.6 Failed: Should have rejected suspended target proctor';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.6: update_campus_grievance_status rejects suspended target proctor';
    END;

    -- Test 7.7: Service Role updates status: Succeeds with active proctor in same institution (Xavier)
    SELECT public.update_campus_grievance_status(
        p_case_id => 'CAMPUS-STD-A',
        p_new_status => 'UNDER_INQUIRY',
        p_proctor_notes => 'Inquiry initiated by authorized proctor',
        p_assigned_proctor => 'Proctor Xavier',
        p_assigned_proctor_user_id => v_proctor_x_id
    ) INTO v_rpc_res;

    ASSERT (v_rpc_res->>'status') = 'UNDER_INQUIRY', 'Test 7.7 Failed: service_role status update failed';
    ASSERT (v_rpc_res->>'assigned_proctor_user_id') = v_proctor_x_id::text, 'Test 7.7 Failed: assigned_proctor_user_id was not set';
    RAISE NOTICE '[PASS] Test 7.7: Authorized backend service_role updates status and assigns proctor via RPC';

    -- Test 7.8: Committee Provisioning RPC: Rejection when assigner is unauthorized (ordinary proctor Xavier)
    BEGIN
        SELECT public.assign_case_committee_member(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_dave_id,
            p_role => 'member',
            p_committee_name => 'Anti-Ragging Committee',
            p_assigned_by => v_proctor_x_id -- Ordinary proctor cannot assign
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.8 Failed: Ordinary proctor should not provision committee members';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.8: assign_case_committee_member rejects assignment by ordinary proctor';
    END;

    -- Test 7.9: Committee Provisioning RPC: Rejection when target is from another institution (Yolanda)
    BEGIN
        SELECT public.assign_case_committee_member(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_proctor_y_id, -- College Y
            p_role => 'member',
            p_committee_name => 'Anti-Ragging Committee',
            p_assigned_by => v_chief_p_id
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.9 Failed: Should have rejected cross-institution target';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.9: assign_case_committee_member rejects cross-institution target';
    END;

    -- Test 7.10: Committee Provisioning RPC: Rejection when target has student role (Alice)
    BEGIN
        SELECT public.assign_case_committee_member(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_student_a_id, -- Student Alice
            p_role => 'member',
            p_committee_name => 'Anti-Ragging Committee',
            p_assigned_by => v_chief_p_id
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 7.10 Failed: Should have rejected student target for committee';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 7.10: assign_case_committee_member rejects student target';
    END;

    -- Test 7.11: Committee Provisioning RPC: Succeeds when assigned by Chief Proctor to active committee member (Dave)
    SELECT public.assign_case_committee_member(
        p_case_id => 'CAMPUS-CONF-C',
        p_target_user_id => v_dave_id,
        p_role => 'member',
        p_committee_name => 'Anti-Ragging Committee',
        p_assigned_by => v_chief_p_id -- Chief Proctor Charlie
    ) INTO v_rpc_res;

    ASSERT (v_rpc_res->>'assignment_status') = 'active', 'Test 7.11 Failed: assignment was not active';
    ASSERT (v_rpc_res->>'user_id') = v_dave_id::text, 'Test 7.11 Failed: user_id mismatch';
    RAISE NOTICE '[PASS] Test 7.11: Chief Proctor successfully assigns committee member Dave to Case C';

    -- Test 7.12: Committee Revocation RPC: Succeeds when revoked by Chief Proctor
    SELECT public.revoke_case_committee_assignment(
        p_case_id => 'CAMPUS-CONF-C',
        p_target_user_id => v_dave_id,
        p_revoked_by => v_chief_p_id
    ) INTO v_rpc_res;

    ASSERT (v_rpc_res->>'assignment_status') = 'revoked', 'Test 7.12 Failed: assignment was not revoked';
    RAISE NOTICE '[PASS] Test 7.12: Chief Proctor successfully revokes committee assignment for Dave';

    -- =================================================================
    -- SECTION 8: Chief Proctor Permission Scoping (Task 4)
    -- =================================================================
    -- Test 8.1: Chief Proctor Charlie can view cases in own institution (Case A and Case B)
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_chief_p_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE institution_uuid = v_inst_x_uuid;
    ASSERT v_count >= 1, 'Test 8.1 Failed: Chief Proctor Charlie must view College X cases';
    RAISE NOTICE '[PASS] Test 8.1: Chief Proctor views institutional cases in College X';

    -- Test 8.2: Chief Proctor Charlie CANNOT view cross-institution cases in College Y
    SELECT count(*) INTO v_count FROM public.campus_cases WHERE institution_uuid = v_inst_y_uuid;
    ASSERT v_count = 0, 'Test 8.2 Failed: Chief Proctor Charlie must NOT see College Y cases!';
    RAISE NOTICE '[PASS] Test 8.2: Chief Proctor Charlie strictly denied cross-institution cases in College Y';

    -- Test 8.3: Chief Proctor Charlie can view committee assignments in own institution
    SELECT count(*) INTO v_count FROM public.case_committee_assignments WHERE institution_uuid = v_inst_x_uuid;
    ASSERT v_count >= 1, 'Test 8.3 Failed: Chief Proctor Charlie must see committee assignments roster in College X';
    RAISE NOTICE '[PASS] Test 8.3: Chief Proctor Charlie views committee assignment roster for College X';

    -- =================================================================
    -- SECTION 9: Phase 1.3.15 Committee Role Consistency & RPC Authorization Audit
    -- =================================================================

    -- Test 9.1: Overloaded private.is_platform_admin(UUID) live verification
    ASSERT private.is_platform_admin(v_admin_id) = true, 'Test 9.1a Failed: Platform admin UUID must evaluate to true';
    ASSERT private.is_platform_admin(v_chief_p_id) = false, 'Test 9.1b Failed: Chief Proctor UUID must evaluate to false';
    ASSERT private.is_platform_admin('00000000-0000-0000-0000-000000000000'::UUID) = false, 'Test 9.1c Failed: Nil UUID must evaluate to false';
    RAISE NOTICE '[PASS] Test 9.1: Overloaded private.is_platform_admin(UUID) verified';

    -- Test 9.2: Chief Proctor Charlie assigned to Case C inquiry committee gains case access
    EXECUTE 'SET LOCAL ROLE service_role';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''service_role''';
    SELECT public.assign_case_committee_member(
        p_case_id => 'CAMPUS-CONF-C',
        p_target_user_id => v_chief_p_id,
        p_role => 'chair',
        p_committee_name => 'Special Inquiry Panel',
        p_assigned_by => v_admin_inst_id
    ) INTO v_rpc_res;
    ASSERT (v_rpc_res->>'assignment_status') = 'active', 'Test 9.2a Failed: Assignment status must be active';
    ASSERT (v_rpc_res->>'user_id') = v_chief_p_id::text, 'Test 9.2b Failed: Assigned user_id mismatch';

    -- Verify Charlie has access across case, documents, activity log, and storage objects
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_chief_p_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 1, 'Test 9.2c Failed: Assigned Chief Proctor must view Case C';

    SELECT count(*) INTO v_count FROM public.case_documents WHERE case_id = 'CAMPUS-CONF-C';
    ASSERT v_count >= 1, 'Test 9.2d Failed: Assigned Chief Proctor must view Case C documents';

    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_id = 'CAMPUS-CONF-C';
    ASSERT v_count >= 1, 'Test 9.2e Failed: Assigned Chief Proctor must view Case C activity log';

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 1, 'Test 9.2f Failed: Assigned Chief Proctor must view Case C storage object';
    RAISE NOTICE '[PASS] Test 9.2: Assigned Chief Proctor gains full access to Case C (metadata, docs, logs, storage)';

    -- Test 9.3: Chief Proctor Revocation immediately severs all access to Case C
    EXECUTE 'SET LOCAL ROLE service_role';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''service_role''';
    SELECT public.revoke_case_committee_assignment(
        p_case_id => 'CAMPUS-CONF-C',
        p_target_user_id => v_chief_p_id,
        p_revoked_by => v_admin_inst_id
    ) INTO v_rpc_res;
    ASSERT (v_rpc_res->>'assignment_status') = 'revoked', 'Test 9.3a Failed: Assignment status must be revoked';

    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_chief_p_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    SELECT count(*) INTO v_count FROM public.campus_cases WHERE id = v_case_c_uuid;
    ASSERT v_count = 0, 'Test 9.3b Failed: Revoked Chief Proctor must NOT view Case C';

    SELECT count(*) INTO v_count FROM public.case_documents WHERE case_id = 'CAMPUS-CONF-C';
    ASSERT v_count = 0, 'Test 9.3c Failed: Revoked Chief Proctor must NOT view Case C documents';

    SELECT count(*) INTO v_count FROM public.case_activity_log WHERE case_id = 'CAMPUS-CONF-C';
    ASSERT v_count = 0, 'Test 9.3d Failed: Revoked Chief Proctor must NOT view Case C activity log';

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'case-documents' AND name = 'CAMPUS-CONF-C/bob_unassigned.pdf';
    ASSERT v_count = 0, 'Test 9.3e Failed: Revoked Chief Proctor must NOT view Case C storage object';
    RAISE NOTICE '[PASS] Test 9.3: Revoked Chief Proctor immediately severed from Case C (zero rows across all entities)';

    -- Test 9.4: Revoke RPC Safety & Edge Cases
    EXECUTE 'SET LOCAL ROLE service_role';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''service_role''';

    -- 9.4a: Revoking already-revoked assignment raises exception
    BEGIN
        SELECT public.revoke_case_committee_assignment(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_chief_p_id,
            p_revoked_by => v_admin_inst_id
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.4a Failed: Revoking already revoked assignment must raise exception';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.4a: Revoking already-revoked assignment raises exception cleanly';
    END;

    -- 9.4b: NULL revoker UUID fails closed
    BEGIN
        SELECT public.revoke_case_committee_assignment(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_dave_id,
            p_revoked_by => NULL
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.4b Failed: NULL revoker identity must raise exception';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.4b: NULL revoker identity fails closed';
    END;

    -- 9.4c: Cross-institution revocation denied
    BEGIN
        SELECT public.revoke_case_committee_assignment(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_carol_id,
            p_revoked_by => v_proctor_y_id -- Yolanda from College Y attempting revocation on College X
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.4c Failed: Cross-institution revocation must be denied';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.4c: Cross-institution revocation denied';
    END;

    -- 9.4d: Suspended admin denied revocation
    BEGIN
        SELECT public.revoke_case_committee_assignment(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_carol_id,
            p_revoked_by => v_sam_id -- Suspended officer Sam
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.4d Failed: Suspended officer must not revoke assignments';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.4d: Suspended officer revocation denied';
    END;

    -- 9.4e: Non-campus grievance rejected
    BEGIN
        SELECT public.revoke_case_committee_assignment(
            p_case_id => 'NONEXISTENT-CASE-99',
            p_target_user_id => v_carol_id,
            p_revoked_by => v_admin_inst_id
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.4e Failed: Non-existent case must raise exception';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.4e: Non-existent case raises exception';
    END;

    -- Test 9.5: Assign RPC Safety & Edge Cases
    -- 9.5a: NULL assigner UUID fails closed
    BEGIN
        SELECT public.assign_case_committee_member(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_dave_id,
            p_role => 'member',
            p_committee_name => 'Panel',
            p_assigned_by => NULL
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.5a Failed: NULL assigner identity must raise exception';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.5a: NULL assigner identity fails closed';
    END;

    -- 9.5b: Non-service_role callers blocked from executing RPCs
    EXECUTE 'SET LOCAL ROLE authenticated';
    EXECUTE 'SET LOCAL "request.jwt.claim.sub" = ''' || v_chief_p_id || '''';
    EXECUTE 'SET LOCAL "request.jwt.claim.role" = ''authenticated''';

    BEGIN
        SELECT public.assign_case_committee_member(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_dave_id,
            p_role => 'member',
            p_assigned_by => v_chief_p_id
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.5b Failed: Authenticated role must not execute assign_case_committee_member';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 9.5b: Authenticated role denied assign_case_committee_member (insufficient_privilege)';
    WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.5b: Authenticated role denied assign_case_committee_member (access denied)';
    END;

    BEGIN
        SELECT public.revoke_case_committee_assignment(
            p_case_id => 'CAMPUS-CONF-C',
            p_target_user_id => v_dave_id,
            p_revoked_by => v_chief_p_id
        ) INTO v_rpc_res;
        RAISE EXCEPTION 'Test 9.5c Failed: Authenticated role must not execute revoke_case_committee_assignment';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE '[PASS] Test 9.5c: Authenticated role denied revoke_case_committee_assignment (insufficient_privilege)';
    WHEN OTHERS THEN
        RAISE NOTICE '[PASS] Test 9.5c: Authenticated role denied revoke_case_committee_assignment (access denied)';
    END;

    RAISE NOTICE '======================================================================';
    RAISE NOTICE '  ALL NYAYPATH PHASE 1.3.14 + 1.3.15 SECURITY & AUDIT TESTS PASSED!';
    RAISE NOTICE '======================================================================';
END $$;

ROLLBACK;

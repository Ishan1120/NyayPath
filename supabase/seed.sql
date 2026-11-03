-- Baseline fixtures for NyayPath Phase 8 and Regression Testing Suites

DO $$
DECLARE
    v_inst_def_uuid  UUID := '00000000-0000-0000-0000-000000000001';
    v_inst_x_uuid    UUID := '11111111-0000-0000-0000-111111111111';
    v_inst_y_uuid    UUID := '22222222-0000-0000-0000-222222222222';

    v_student_a_id   UUID := 'aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa';
    v_student_b_id   UUID := 'bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb';
    v_proctor_x_id   UUID := 'cccccccc-1111-2222-3333-cccccccccccc';
    v_carol_id       UUID := 'eeeeeeee-1111-2222-3333-eeeeeeeeeeee';
    v_chief_p_id     UUID := '66666666-1111-2222-3333-666666666666';
    v_admin_inst_id  UUID := '44444444-1111-2222-3333-444444444444';
    v_sam_id         UUID := 'ffffffff-1111-2222-3333-ffffffffffff';
    v_chief_y_id     UUID := 'dddddddd-1111-2222-3333-dddddddddddd';
    v_admin_y_id     UUID := '33333333-1111-2222-3333-333333333333';
    v_platform_id    UUID := '99999999-1111-2222-3333-999999999999';
    v_lawyer_a_id    UUID := '77777777-1111-2222-3333-777777777777';
    v_lawyer_b_id    UUID := '88888888-1111-2222-3333-888888888888';

    -- Phase 2.1 - 2.3 Legacy Test Actors
    v_p2_student_10  UUID := '00000000-0000-4000-8000-000000000010';
    v_p2_citizen_20  UUID := '00000000-0000-4000-8000-000000000020';
    v_p2_proctor_01  UUID := '00000000-0000-4000-8000-000000000001';

    v_case_c_uuid    UUID := 'c3333333-0000-0000-0000-000000000003';
    v_case_y_uuid    UUID := 'd4444444-0000-0000-0000-000000000004';
BEGIN
    -- 1. Insert institutions
    INSERT INTO public.institutions (id, code, name, city, state, type)
    VALUES
        (v_inst_def_uuid, 'INST_DEFAULT', 'Default Central Institution', 'New Delhi', 'Delhi', 'university'),
        (v_inst_x_uuid, 'INST_COLLEGE_X', 'National Institute of Technology X', 'Durgapur', 'West Bengal', 'university'),
        (v_inst_y_uuid, 'INST_COLLEGE_Y', 'Indian Institute of Technology Y', 'Mumbai', 'Maharashtra', 'university')
    ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name;

    -- 2. Insert auth.users
    INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, is_super_admin, created_at, updated_at)
    VALUES
        (v_student_a_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'alice@collegex.edu', 'mock_encrypted_hash', now(), '{"role":"student","institution_id":"INST_COLLEGE_X","account_status":"active"}'::jsonb, '{"full_name":"Alice Student"}'::jsonb, false, now(), now()),
        (v_student_b_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'bob@collegex.edu', 'mock_encrypted_hash', now(), '{"role":"student","institution_id":"INST_COLLEGE_X","account_status":"active"}'::jsonb, '{"full_name":"Bob Student"}'::jsonb, false, now(), now()),
        (v_proctor_x_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'xavier@collegex.edu', 'mock_encrypted_hash', now(), '{"role":"proctor","institution_id":"INST_COLLEGE_X","account_status":"active"}'::jsonb, '{"full_name":"Xavier Proctor"}'::jsonb, false, now(), now()),
        (v_carol_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'carol@collegex.edu', 'mock_encrypted_hash', now(), '{"role":"committee_member","institution_id":"INST_COLLEGE_X","account_status":"active"}'::jsonb, '{"full_name":"Carol Committee"}'::jsonb, false, now(), now()),
        (v_chief_p_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'charlie@collegex.edu', 'mock_encrypted_hash', now(), '{"role":"chief_proctor","institution_id":"INST_COLLEGE_X","account_status":"active"}'::jsonb, '{"full_name":"Charlie Chief Proctor"}'::jsonb, false, now(), now()),
        (v_admin_inst_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'irene@collegex.edu', 'mock_encrypted_hash', now(), '{"role":"institution_admin","institution_id":"INST_COLLEGE_X","account_status":"active"}'::jsonb, '{"full_name":"Irene Inst Admin"}'::jsonb, false, now(), now()),
        (v_sam_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'sam@collegex.edu', 'mock_encrypted_hash', now(), '{"role":"institution_admin","institution_id":"INST_COLLEGE_X","account_status":"suspended"}'::jsonb, '{"full_name":"Sam Suspended Admin"}'::jsonb, false, now(), now()),
        (v_chief_y_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'yolanda@collegey.edu', 'mock_encrypted_hash', now(), '{"role":"chief_proctor","institution_id":"INST_COLLEGE_Y","account_status":"active"}'::jsonb, '{"full_name":"Yolanda Chief Proctor Y"}'::jsonb, false, now(), now()),
        (v_admin_y_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'adminy@collegey.edu', 'mock_encrypted_hash', now(), '{"role":"institution_admin","institution_id":"INST_COLLEGE_Y","account_status":"active"}'::jsonb, '{"full_name":"Admin Y"}'::jsonb, false, now(), now()),
        (v_platform_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'platform@nyaypath.gov', 'mock_encrypted_hash', now(), '{"role":"platform_admin","account_status":"active"}'::jsonb, '{"full_name":"Platform Administrator"}'::jsonb, true, now(), now()),
        (v_lawyer_a_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'advocate.rajesh@bar.in', 'mock_encrypted_hash', now(), '{"role":"lawyer","account_status":"active"}'::jsonb, '{"full_name":"Adv. Rajesh Kumar"}'::jsonb, false, now(), now()),
        (v_lawyer_b_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'advocate.priya@bar.in', 'mock_encrypted_hash', now(), '{"role":"lawyer","account_status":"active"}'::jsonb, '{"full_name":"Adv. Priya Sharma"}'::jsonb, false, now(), now()),
        -- Phase 2 legacy actors
        (v_p2_student_10, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'student@nit.edu', 'mock_encrypted_hash', now(), '{"role":"student","institution_id":"INST_DEFAULT","account_status":"active"}'::jsonb, '{"full_name":"Aarav Sharma"}'::jsonb, false, now(), now()),
        (v_p2_citizen_20, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'citizen@nyaypath.in', 'mock_encrypted_hash', now(), '{"role":"citizen","institution_id":"INST_DEFAULT","account_status":"active"}'::jsonb, '{"full_name":"Priya Patel"}'::jsonb, false, now(), now()),
        (v_p2_proctor_01, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'proctor@institution.edu', 'mock_encrypted_hash', now(), '{"role":"proctor","institution_id":"INST_DEFAULT","account_status":"active"}'::jsonb, '{"full_name":"Default Proctor"}'::jsonb, false, now(), now())
    ON CONFLICT (id) DO UPDATE SET raw_app_meta_data = EXCLUDED.raw_app_meta_data;

    -- 3. Insert profiles
    INSERT INTO public.profiles (id, email, full_name, role) VALUES
        (v_student_a_id, 'alice@collegex.edu', 'Alice Student', 'student'),
        (v_student_b_id, 'bob@collegex.edu', 'Bob Student', 'student'),
        (v_proctor_x_id, 'xavier@collegex.edu', 'Xavier Proctor', 'proctor'),
        (v_carol_id, 'carol@collegex.edu', 'Carol Committee', 'committee_member'),
        (v_chief_p_id, 'charlie@collegex.edu', 'Charlie Chief Proctor', 'chief_proctor'),
        (v_admin_inst_id, 'irene@collegex.edu', 'Irene Inst Admin', 'institution_admin'),
        (v_sam_id, 'sam@collegex.edu', 'Sam Suspended Admin', 'institution_admin'),
        (v_chief_y_id, 'yolanda@collegey.edu', 'Yolanda Chief Proctor Y', 'chief_proctor'),
        (v_admin_y_id, 'adminy@collegey.edu', 'Admin Y', 'institution_admin'),
        (v_platform_id, 'platform@nyaypath.gov', 'Platform Administrator', 'platform_admin'),
        (v_lawyer_a_id, 'advocate.rajesh@bar.in', 'Adv. Rajesh Kumar', 'lawyer'),
        (v_lawyer_b_id, 'advocate.priya@bar.in', 'Adv. Priya Sharma', 'lawyer'),
        (v_p2_student_10, 'student@nit.edu', 'Aarav Sharma', 'student'),
        (v_p2_citizen_20, 'citizen@nyaypath.in', 'Priya Patel', 'citizen'),
        (v_p2_proctor_01, 'proctor@institution.edu', 'Default Proctor', 'proctor')
    ON CONFLICT (id) DO UPDATE SET role = EXCLUDED.role;

    -- 4. Platform admins
    INSERT INTO public.platform_admins (user_id, email, account_status)
    VALUES (v_platform_id, 'platform@nyaypath.gov', 'active')
    ON CONFLICT (user_id) DO UPDATE SET account_status = 'active', email = EXCLUDED.email;

    -- 4b. Lawyer Profiles
    INSERT INTO public.lawyer_profiles (
        id, full_name, email, bar_council, enrollment_state, enrollment_number, years_of_practice, verification_status, verified_at
    ) VALUES (
        v_lawyer_a_id, 'Adv. Rajesh Kumar', 'advocate.rajesh@bar.in', 'Bar Council of Delhi', 'Delhi', 'D/1234/2015', 9, 'VERIFIED', now()
    ) ON CONFLICT (id) DO UPDATE SET verification_status = 'VERIFIED';

    -- 5. Institution Memberships
    INSERT INTO public.institution_memberships (user_id, institution_id, institution_code, role, account_status)
    VALUES
        (v_proctor_x_id, v_inst_x_uuid, 'INST_COLLEGE_X', 'proctor', 'active'),
        (v_carol_id, v_inst_x_uuid, 'INST_COLLEGE_X', 'committee_member', 'active'),
        (v_chief_p_id, v_inst_x_uuid, 'INST_COLLEGE_X', 'chief_proctor', 'active'),
        (v_admin_inst_id, v_inst_x_uuid, 'INST_COLLEGE_X', 'institution_admin', 'active'),
        (v_sam_id, v_inst_x_uuid, 'INST_COLLEGE_X', 'institution_admin', 'suspended'),
        (v_chief_y_id, v_inst_y_uuid, 'INST_COLLEGE_Y', 'chief_proctor', 'active'),
        (v_admin_y_id, v_inst_y_uuid, 'INST_COLLEGE_Y', 'institution_admin', 'active'),
        (v_p2_proctor_01, v_inst_def_uuid, 'INST_DEFAULT', 'proctor', 'active')
    ON CONFLICT (user_id, institution_id) DO UPDATE SET role = EXCLUDED.role, account_status = EXCLUDED.account_status;

    -- 6. Campus Cases (trigger automatically creates parent cases row)
    INSERT INTO public.campus_cases (
        id, case_id, institution_id, institution_uuid, student_user_id, student_name,
        department, year, category, subject, description, is_anonymous, confidentiality_mode,
        severity, status, verification_key_hash
    ) VALUES
        (v_case_c_uuid, 'CAMPUS-CONF-C', 'INST_COLLEGE_X', v_inst_x_uuid, v_student_b_id, 'Bob Student',
         'MECH', '4th', 'DISCRIMINATION', 'Confidential Inquiry C', 'Sensitive inquiry desc', FALSE, 'CONFIDENTIAL',
         'HIGH', 'UNDER_INQUIRY', 'MOCK_HASH_C'),
        (v_case_y_uuid, 'CAMPUS-INST-Y', 'INST_COLLEGE_Y', v_inst_y_uuid, v_student_a_id, 'Alice Student',
         'CSE', '2nd', 'ACADEMIC', 'College Y Case', 'College Y case desc', FALSE, 'STANDARD',
         'NORMAL', 'UNDER_INQUIRY', 'MOCK_HASH_Y')
    ON CONFLICT (id) DO UPDATE SET
        confidentiality_mode = EXCLUDED.confidentiality_mode,
        status = EXCLUDED.status;

    -- 7. Document metadata for Case C
    INSERT INTO public.case_documents (
        id, case_uuid, case_id, file_name, file_size_bytes, mime_type, storage_path, uploader_user_id, is_confidential
    ) VALUES (
        '33333333-3333-3333-3333-333333333333', v_case_c_uuid, 'CAMPUS-CONF-C', 'confidential_evidence.pdf',
        2048, 'application/pdf', 'CAMPUS-CONF-C/confidential_evidence.pdf', v_student_b_id, TRUE
    ) ON CONFLICT (id) DO NOTHING;

    -- 8. Case committee assignment for Charlie Chief Proctor on Case C
    INSERT INTO public.case_committee_assignments (
        case_uuid, case_id, user_id, institution_uuid, committee_name, role, assignment_status, assigned_by
    ) VALUES (
        v_case_c_uuid, 'CAMPUS-CONF-C', v_chief_p_id, v_inst_x_uuid, 'Disciplinary Committee', 'chair', 'active', v_admin_inst_id
    ) ON CONFLICT (case_uuid, user_id) DO UPDATE SET assignment_status = 'active';

    -- Notify PostgREST to reload schema
    NOTIFY pgrst, 'reload schema';
END $$;

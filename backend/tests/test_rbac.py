from app.core.rbac import MFA_REQUIRED_ROLES, ROLE_PERMISSIONS, P, Role, mfa_required, permissions_for


def test_permission_matrix():
    # Spec §2.3: the System Admin configures the system but has no access to student records.
    # Nor does it touch money or approve anything.
    records_and_money = {
        P.STUDENTS_READ,
        P.STUDENTS_MANAGE,
        P.STUDENTS_IMPORT,
        P.FEES_READ,
        P.FEES_MANAGE,
        P.FEES_COLLECT,
        P.APPROVALS_DECIDE,
        P.MESSAGES_READ,  # the delivery log names students and parents
        P.ADMISSIONS_READ,  # applicants' personal data
        P.ADMISSIONS_MANAGE,
        *(P.LIBRARY_MANAGE, P.LIBRARY_READ, P.HOSTEL_MANAGE, P.HOSTEL_READ, P.PLACEMENT_MANAGE, P.PLACEMENT_READ),
        *(P.GRIEVANCE_MANAGE, P.GRIEVANCE_READ, P.GRIEVANCE_SENSITIVE),  # complaints name students
        *(P.STAFF_READ, P.STAFF_READ_DEPT, P.STAFF_MANAGE, P.LEAVE_APPROVE),  # staff records are HR's
        *(P.REPORTS_READ, P.NAAC_MANAGE),  # reports carry student and staff data
    }
    # Nor does it run the academic side (timetable, attendance).
    academics = {
        P.TIMETABLE_READ,
        P.TIMETABLE_MANAGE,
        P.TIMETABLE_MANAGE_DEPT,
        P.ATTENDANCE_TAKE,
        P.ATTENDANCE_READ,
        P.ATTENDANCE_READ_DEPT,
        P.ATTENDANCE_APPROVE,
        P.ATTENDANCE_EXEMPT,
        P.MARKS_ENTER,
        P.MARKS_APPROVE,
        P.MARKS_SCHEME_DEPT,
        P.MARKS_READ,
        P.EXAMS_MANAGE,
        P.RESULTS_READ,
        P.CERT_MANAGE,
        P.CERT_SIGN_PRINCIPAL,
        P.CERT_SIGN_HOD,
        P.CERT_READ,
    }
    assert permissions_for(["system_admin"]) == frozenset(P) - records_and_money - academics
    assert permissions_for(["principal"]) == {
        P.ANALYTICS_VIEW,
        P.AUDIT_READ,
        P.USERS_READ,
        P.SETUP_READ,
        P.STUDENTS_READ,
        P.FEES_READ,
        P.APPROVALS_DECIDE,
        P.NOTICES_READ,
        P.NOTICES_PUBLISH,
        P.TIMETABLE_READ,
        P.ATTENDANCE_READ,
        P.MARKS_READ,
        P.RESULTS_READ,
        P.CERT_READ,
        P.CERT_SIGN_PRINCIPAL,
        P.MESSAGES_READ,
        P.ADMISSIONS_READ,
        P.LIBRARY_READ,
        P.HOSTEL_READ,
        P.PLACEMENT_READ,
        P.GRIEVANCE_READ,
        P.STAFF_READ,
        P.LEAVE_APPLY,
        P.LEAVE_APPROVE,
        P.REPORTS_READ,
    }
    assert P.USERS_CREATE_STAFF not in permissions_for(["office"])
    assert P.USERS_CREATE_STUDENT in permissions_for(["office"])
    assert permissions_for(["accounts"]) == {
        P.SETUP_READ,
        P.NOTICES_READ,
        P.NOTICES_PUBLISH,
        P.CERT_READ,
        P.STUDENTS_READ,
        P.FEES_READ,
        P.FEES_MANAGE,
        P.FEES_COLLECT,
        P.MESSAGES_READ,
        P.ADMISSIONS_READ,
        P.LEAVE_APPLY,
    }
    assert permissions_for(["faculty"]) == {
        P.SETUP_READ,
        P.NOTICES_READ,
        P.LEAVE_APPLY,
        P.TIMETABLE_READ,
        P.ATTENDANCE_TAKE,
        P.MARKS_ENTER,
    }
    assert P.EXAMS_MANAGE in permissions_for(["exam_cell"]) and P.MARKS_ENTER not in permissions_for(["exam_cell"])
    assert P.TIMETABLE_MANAGE_DEPT in permissions_for(["hod"]) and P.TIMETABLE_MANAGE not in permissions_for(["hod"])
    assert P.ADMISSIONS_MANAGE in permissions_for(["admission"])
    assert P.LIBRARY_MANAGE in permissions_for(["librarian"]) and P.STUDENTS_READ not in permissions_for(["librarian"])
    assert P.HOSTEL_MANAGE in permissions_for(["warden"]) and P.PLACEMENT_MANAGE in permissions_for(["placement"])
    # Sensitive grievances (ragging, harassment) only reach the ICC, not even the Principal.
    sensitive = {role for role, perms in ROLE_PERMISSIONS.items() if P.GRIEVANCE_SENSITIVE in perms}
    assert sensitive == {Role.ICC}
    assert P.GRIEVANCE_MANAGE in permissions_for(["grievance"]) and P.STUDENTS_READ not in permissions_for(["icc"])
    assert {P.STAFF_MANAGE, P.STAFF_READ} <= permissions_for(["office"])
    assert {P.STAFF_READ_DEPT, P.LEAVE_APPROVE} <= permissions_for(["hod"])
    for role in (Role.STUDENT, Role.PARENT, Role.APPLICANT):
        assert permissions_for([role.value]) == frozenset(), role


def test_only_system_admin_changes_setup():
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if P.SETUP_MANAGE in perms}
    assert holders == {Role.SYSTEM_ADMIN}


def test_roles_combine_and_unknown_roles_grant_nothing():
    assert permissions_for(["office", "principal"]) == permissions_for(["office"]) | permissions_for(["principal"])
    assert permissions_for(["superuser", "root"]) == frozenset()


def test_only_the_principal_reads_audit_besides_admins():
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if P.AUDIT_READ in perms}
    assert holders == {Role.SYSTEM_ADMIN, Role.PRINCIPAL}


def test_mfa_required_for_money_marks_and_admin_roles():
    assert {Role.SYSTEM_ADMIN, Role.PRINCIPAL, Role.ACCOUNTS, Role.EXAM_CELL} == MFA_REQUIRED_ROLES
    assert mfa_required(["faculty", "accounts"]) and not mfa_required(["faculty", "office"])


def test_only_office_changes_student_records():
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if P.STUDENTS_MANAGE in perms}
    assert holders == {Role.OFFICE}


def test_money_roles():
    collect = {role for role, perms in ROLE_PERMISSIONS.items() if P.FEES_COLLECT in perms}
    approve = {role for role, perms in ROLE_PERMISSIONS.items() if P.APPROVALS_DECIDE in perms}
    assert collect == {Role.ACCOUNTS} and approve == {Role.PRINCIPAL}
    assert collect | approve <= MFA_REQUIRED_ROLES  # both must use 2-step verification

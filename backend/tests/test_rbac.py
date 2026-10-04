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
    }
    assert permissions_for(["system_admin"]) == frozenset(P) - records_and_money
    assert permissions_for(["principal"]) == {
        P.ANALYTICS_VIEW,
        P.AUDIT_READ,
        P.USERS_READ,
        P.SETUP_READ,
        P.STUDENTS_READ,
        P.FEES_READ,
        P.APPROVALS_DECIDE,
    }
    assert P.USERS_CREATE_STAFF not in permissions_for(["office"])
    assert P.USERS_CREATE_STUDENT in permissions_for(["office"])
    assert permissions_for(["accounts"]) == {P.SETUP_READ, P.STUDENTS_READ, P.FEES_READ, P.FEES_MANAGE, P.FEES_COLLECT}
    assert permissions_for(["faculty"]) == {P.SETUP_READ}
    for role in (Role.STUDENT, Role.PARENT):
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

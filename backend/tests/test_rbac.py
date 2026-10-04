from app.core.rbac import MFA_REQUIRED_ROLES, ROLE_PERMISSIONS, P, Role, mfa_required, permissions_for


def test_permission_matrix():
    assert permissions_for(["system_admin"]) == frozenset(P)
    assert permissions_for(["principal"]) == {P.ANALYTICS_VIEW, P.AUDIT_READ, P.USERS_READ}
    assert P.USERS_CREATE_STAFF not in permissions_for(["office"])
    assert P.USERS_CREATE_STUDENT in permissions_for(["office"])
    for role in (Role.STUDENT, Role.PARENT, Role.FACULTY, Role.ACCOUNTS):
        assert permissions_for([role.value]) == frozenset(), role


def test_roles_combine_and_unknown_roles_grant_nothing():
    assert permissions_for(["office", "principal"]) == permissions_for(["office"]) | permissions_for(["principal"])
    assert permissions_for(["superuser", "root"]) == frozenset()


def test_only_the_principal_reads_audit_besides_admins():
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if P.AUDIT_READ in perms}
    assert holders == {Role.SYSTEM_ADMIN, Role.PRINCIPAL}


def test_mfa_required_for_money_marks_and_admin_roles():
    assert {Role.SYSTEM_ADMIN, Role.PRINCIPAL, Role.ACCOUNTS, Role.EXAM_CELL} == MFA_REQUIRED_ROLES
    assert mfa_required(["faculty", "accounts"]) and not mfa_required(["faculty", "office"])

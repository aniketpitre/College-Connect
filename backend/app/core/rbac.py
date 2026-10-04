"""
Roles and permissions (product spec §2.3).

Every endpoint declares the permission it needs with `Depends(require("..."))`. Scope
(which students or classes a user may see) is checked separately in each module's
service layer. Permissions are added here as each module is built.
"""

from enum import StrEnum


class Role(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    PRINCIPAL = "principal"
    OFFICE = "office"
    ACCOUNTS = "accounts"
    ADMISSION = "admission"
    EXAM_CELL = "exam_cell"
    HOD = "hod"
    FACULTY = "faculty"
    MENTOR = "mentor"
    LIBRARIAN = "librarian"
    WARDEN = "warden"
    PLACEMENT = "placement"
    STUDENT = "student"
    PARENT = "parent"


STAFF_ROLES = frozenset(Role) - {Role.STUDENT, Role.PARENT}

# Roles that handle money, marks or accounts must use 2-step verification (spec §2.1).
MFA_REQUIRED_ROLES = frozenset({Role.SYSTEM_ADMIN, Role.PRINCIPAL, Role.ACCOUNTS, Role.EXAM_CELL})

ROLE_LABELS: dict[Role, str] = {
    Role.SYSTEM_ADMIN: "System Admin",
    Role.PRINCIPAL: "Principal",
    Role.OFFICE: "Office",
    Role.ACCOUNTS: "Accounts",
    Role.ADMISSION: "Admission Cell",
    Role.EXAM_CELL: "Exam Cell",
    Role.HOD: "HOD",
    Role.FACULTY: "Faculty",
    Role.MENTOR: "Mentor",
    Role.LIBRARIAN: "Librarian",
    Role.WARDEN: "Hostel Warden",
    Role.PLACEMENT: "Placement Officer",
    Role.STUDENT: "Student",
    Role.PARENT: "Parent",
}


class P(StrEnum):
    """Permission names: <area>.<action>."""

    ANALYTICS_VIEW = "analytics.view"
    AUDIT_READ = "audit.read"
    USERS_READ = "users.read"
    USERS_CREATE_STAFF = "users.create.staff"
    USERS_CREATE_STUDENT = "users.create.student"
    USERS_UPDATE = "users.update"
    USERS_MANAGE_ROLES = "users.roles.manage"
    USERS_RESET_STAFF = "users.reset_password.staff"
    USERS_RESET_STUDENT = "users.reset_password.student"
    SETUP_READ = "setup.read"
    SETUP_MANAGE = "setup.manage"
    STUDENTS_READ = "students.read"
    STUDENTS_MANAGE = "students.manage"
    STUDENTS_IMPORT = "students.import"
    FEES_READ = "fees.read"
    FEES_MANAGE = "fees.manage"  # heads, structures, demands, scholarships, charges, opening balances
    FEES_COLLECT = "fees.collect"  # counter collection; also requests concessions, cancellations, refunds
    APPROVALS_DECIDE = "approvals.decide"
    NOTICES_READ = "notices.read"
    NOTICES_PUBLISH = "notices.publish"
    EXPORT_REQUEST = "export.request"  # full CSV exports; each needs the Principal's approval


# Every staff member can read the college structure (programmes, divisions, subjects…).
_STAFF_BASE = frozenset({P.SETUP_READ, P.NOTICES_READ})
# Spec §2.3 "Notices": admin, principal and office publish; accounts, admission and exam cell publish
# their own notices. HOD/faculty (department / own class) come with class assignments in Phase 2.
_PUBLISH = frozenset({P.NOTICES_PUBLISH})

ROLE_PERMISSIONS: dict[Role, frozenset[P]] = {
    Role.SYSTEM_ADMIN: _STAFF_BASE
    | {
        P.ANALYTICS_VIEW,
        P.AUDIT_READ,
        P.USERS_READ,
        P.USERS_CREATE_STAFF,
        P.USERS_CREATE_STUDENT,
        P.USERS_UPDATE,
        P.USERS_MANAGE_ROLES,
        P.USERS_RESET_STAFF,
        P.USERS_RESET_STUDENT,
        P.SETUP_MANAGE,
        P.EXPORT_REQUEST,
    }
    | _PUBLISH,
    Role.PRINCIPAL: _STAFF_BASE
    | {P.ANALYTICS_VIEW, P.AUDIT_READ, P.USERS_READ, P.STUDENTS_READ, P.FEES_READ, P.APPROVALS_DECIDE}
    | _PUBLISH,
    Role.OFFICE: _STAFF_BASE
    | {
        P.ANALYTICS_VIEW,
        P.USERS_READ,
        P.USERS_CREATE_STUDENT,
        P.USERS_UPDATE,
        P.USERS_RESET_STUDENT,
        P.STUDENTS_READ,
        P.STUDENTS_MANAGE,
        P.STUDENTS_IMPORT,
        P.FEES_READ,
    }
    | _PUBLISH,
    Role.ACCOUNTS: _STAFF_BASE | {P.STUDENTS_READ, P.FEES_READ, P.FEES_MANAGE, P.FEES_COLLECT} | _PUBLISH,
    # Read the student master (spec §2.3). HOD/faculty/mentor get scoped access with class
    # assignments in Phase 2.
    **{role: _STAFF_BASE | {P.STUDENTS_READ} | _PUBLISH for role in (Role.ADMISSION, Role.EXAM_CELL)},
    **{
        role: _STAFF_BASE
        for role in (
            Role.HOD,
            Role.FACULTY,
            Role.MENTOR,
            Role.LIBRARIAN,
            Role.WARDEN,
            Role.PLACEMENT,
        )
    },
}


def permissions_for(roles: list[str]) -> frozenset[P]:
    granted: set[P] = set()
    for name in roles:
        try:
            granted |= ROLE_PERMISSIONS.get(Role(name), frozenset())
        except ValueError:
            continue  # unknown role names grant nothing
    return frozenset(granted)


def mfa_required(roles: list[str]) -> bool:
    return any(r in MFA_REQUIRED_ROLES for r in roles)

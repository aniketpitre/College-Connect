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
    GRIEVANCE = "grievance"  # Grievance Redressal Cell
    ICC = "icc"  # Internal Complaints Committee / Anti-ragging: sensitive grievances only
    IQAC = "iqac"  # IQAC coordinator: NAAC evidence and reports
    STUDENT = "student"
    PARENT = "parent"
    APPLICANT = "applicant"  # someone applying for admission (online application only)


STAFF_ROLES = frozenset(Role) - {Role.STUDENT, Role.PARENT, Role.APPLICANT}

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
    Role.GRIEVANCE: "Grievance Cell",
    Role.ICC: "ICC / Anti-ragging",
    Role.IQAC: "IQAC Coordinator",
    Role.STUDENT: "Student",
    Role.PARENT: "Parent",
    Role.APPLICANT: "Applicant",
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
    TIMETABLE_READ = "timetable.read"
    TIMETABLE_MANAGE = "timetable.manage"  # every division
    TIMETABLE_MANAGE_DEPT = "timetable.manage.dept"  # HOD: divisions of their own department
    ATTENDANCE_TAKE = "attendance.take"  # lectures they teach (or substitute for)
    ATTENDANCE_READ = "attendance.read"  # every division
    ATTENDANCE_READ_DEPT = "attendance.read.dept"  # HOD: their own department
    ATTENDANCE_APPROVE = "attendance.approve"  # HOD: edits after the 48-hour window, own department
    ATTENDANCE_EXEMPT = "attendance.exempt"  # office: medical / official-duty exemptions
    MARKS_ENTER = "marks.enter"  # internal marks of the subjects they teach
    MARKS_APPROVE = "marks.approve"  # HOD: approve / return marks of their department
    MARKS_SCHEME_DEPT = "marks.scheme.dept"  # HOD: assessment schemes of their department
    MARKS_READ = "marks.read"  # every class
    EXAMS_MANAGE = "exams.manage"  # Exam Cell: schemes, deadlines, lock, Upload Guard, forms, hall tickets, results
    RESULTS_READ = "results.read"
    CERT_MANAGE = "certificates.manage"  # office: verify, sign office certificates, issue, reject
    CERT_SIGN_PRINCIPAL = "certificates.sign.principal"  # TC, migration
    CERT_SIGN_HOD = "certificates.sign.hod"  # department-level certificates (internship NOC)
    CERT_READ = "certificates.read"  # accounts (no-dues), principal
    ADMISSIONS_READ = "admissions.read"
    ADMISSIONS_MANAGE = "admissions.manage"  # cycles, scrutiny, merit rounds, confirm and cancel admissions
    LIBRARY_MANAGE = "library.manage"  # catalogue, issue/return, fines, settings
    LIBRARY_READ = "library.read"
    HOSTEL_MANAGE = "hostel.manage"  # rooms, allotment, out-passes, complaints, mess menu
    HOSTEL_READ = "hostel.read"
    PLACEMENT_MANAGE = "placement.manage"  # drives, registrations, rounds, offers
    PLACEMENT_READ = "placement.read"
    GRIEVANCE_MANAGE = "grievance.manage"  # ordinary grievances: take, reply, resolve; time limits
    GRIEVANCE_READ = "grievance.read"  # ordinary grievances, read-only (sensitive ones only as counts)
    GRIEVANCE_SENSITIVE = "grievance.sensitive"  # ragging / harassment cases (ICC members only)
    STAFF_READ = "staff.read"  # staff records, workload, leave of everyone
    STAFF_READ_DEPT = "staff.read.dept"  # HOD: their own department
    STAFF_MANAGE = "staff.manage"  # staff records, qualifications, leave types and adjustments
    LEAVE_APPLY = "leave.apply"  # every staff member
    LEAVE_APPROVE = "leave.approve"  # HOD (their department's staff), Principal (HODs, others)
    REPORTS_READ = "reports.read"  # NAAC / AQAR tables, AISHE, NIRF, APAAR checks and ABC credit export
    NAAC_MANAGE = "naac.manage"  # NAAC evidence uploads and settings (sanctioned posts, intake)
    MENTEES = "mentoring.mentees"  # their own mentees: risk reasons and counselling notes
    MENTOR_ASSIGN = "mentoring.assign"  # set students' mentors (office: any class; HOD: their department)
    RISK_READ = "risk.read"  # early-warning list for the whole college (Principal)
    RISK_READ_DEPT = "risk.read.dept"  # early-warning list for their department (HOD)
    RISK_MANAGE = "risk.manage"  # early-warning rules, recompute now
    API_KEYS_MANAGE = "api_keys.manage"  # keys for the open read-only API (other systems)
    MESSAGES_READ = "messages.read"  # the delivery log and the outgoing message queue
    EXPORT_REQUEST = "export.request"  # full CSV exports; each needs the Principal's approval
    KB_MANAGE = "kb.manage"  # help-desk documents: add, remove, re-index


# Every staff member can read the college structure (programmes, divisions, subjects…).
_STAFF_BASE = frozenset({P.SETUP_READ, P.NOTICES_READ, P.LEAVE_APPLY})
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
        P.KB_MANAGE,
    }
    | _PUBLISH,
    Role.PRINCIPAL: _STAFF_BASE
    | {
        P.ANALYTICS_VIEW,
        P.AUDIT_READ,
        P.USERS_READ,
        P.STUDENTS_READ,
        P.FEES_READ,
        P.APPROVALS_DECIDE,
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
        P.LEAVE_APPROVE,
        P.REPORTS_READ,
        P.RISK_READ,
        P.RISK_MANAGE,
        P.API_KEYS_MANAGE,
    }
    | _PUBLISH,
    Role.OFFICE: _STAFF_BASE
    | {
        P.ANALYTICS_VIEW,
        P.KB_MANAGE,
        P.USERS_READ,
        P.USERS_CREATE_STUDENT,
        P.USERS_UPDATE,
        P.USERS_RESET_STUDENT,
        P.STUDENTS_READ,
        P.STUDENTS_MANAGE,
        P.STUDENTS_IMPORT,
        P.FEES_READ,
        P.TIMETABLE_READ,
        P.TIMETABLE_MANAGE,
        P.ATTENDANCE_READ,
        P.ATTENDANCE_EXEMPT,
        P.RESULTS_READ,
        P.CERT_MANAGE,
        P.CERT_READ,
        P.MESSAGES_READ,
        P.ADMISSIONS_READ,
        P.STAFF_READ,
        P.STAFF_MANAGE,
        P.REPORTS_READ,
        P.MENTOR_ASSIGN,
    }
    | _PUBLISH,
    Role.ACCOUNTS: _STAFF_BASE
    | {P.STUDENTS_READ, P.FEES_READ, P.FEES_MANAGE, P.FEES_COLLECT, P.CERT_READ, P.MESSAGES_READ, P.ADMISSIONS_READ}
    | _PUBLISH,
    # Read the student master (spec §2.3). HOD/faculty/mentor get scoped access with class
    # assignments in Phase 2.
    Role.ADMISSION: _STAFF_BASE | {P.STUDENTS_READ, P.ADMISSIONS_READ, P.ADMISSIONS_MANAGE} | _PUBLISH,
    Role.EXAM_CELL: _STAFF_BASE
    | {P.STUDENTS_READ, P.TIMETABLE_READ, P.ATTENDANCE_READ, P.MARKS_READ, P.EXAMS_MANAGE, P.RESULTS_READ}
    | _PUBLISH,
    # Phase 2: HOD builds the department timetable and sees department attendance; faculty and
    # mentors take attendance for the lectures they teach.
    Role.HOD: _STAFF_BASE
    | {
        P.TIMETABLE_READ,
        P.TIMETABLE_MANAGE_DEPT,
        P.ATTENDANCE_TAKE,
        P.ATTENDANCE_READ_DEPT,
        P.ATTENDANCE_APPROVE,
        P.MARKS_ENTER,
        P.MARKS_APPROVE,
        P.MARKS_SCHEME_DEPT,
        P.CERT_SIGN_HOD,
        P.STAFF_READ_DEPT,
        P.LEAVE_APPROVE,
        P.MENTEES,
        P.MENTOR_ASSIGN,
        P.RISK_READ_DEPT,
    },
    Role.FACULTY: _STAFF_BASE | {P.TIMETABLE_READ, P.ATTENDANCE_TAKE, P.MARKS_ENTER},
    Role.MENTOR: _STAFF_BASE | {P.TIMETABLE_READ, P.ATTENDANCE_TAKE, P.MARKS_ENTER, P.MENTEES},
    Role.LIBRARIAN: _STAFF_BASE | {P.LIBRARY_MANAGE, P.LIBRARY_READ} | _PUBLISH,
    Role.WARDEN: _STAFF_BASE | {P.HOSTEL_MANAGE, P.HOSTEL_READ} | _PUBLISH,
    Role.PLACEMENT: _STAFF_BASE | {P.PLACEMENT_MANAGE, P.PLACEMENT_READ, P.RESULTS_READ} | _PUBLISH,
    Role.GRIEVANCE: _STAFF_BASE | {P.GRIEVANCE_MANAGE, P.GRIEVANCE_READ},
    Role.ICC: _STAFF_BASE | {P.GRIEVANCE_SENSITIVE},
    Role.IQAC: _STAFF_BASE | {P.REPORTS_READ, P.NAAC_MANAGE, P.STAFF_READ},
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

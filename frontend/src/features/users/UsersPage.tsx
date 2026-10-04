import { useState } from "react";
import { Link } from "react-router";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable, type Column } from "../../components/DataTable";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError } from "../../lib/api";
import { hasPermission, useMe } from "../../lib/auth";
import {
  useCreateUser,
  useResetPassword,
  useResetTwoStep,
  useRoles,
  useUnlockUser,
  useUpdateUser,
  useUsers,
  type NewUser,
  type RoleInfo,
  type User,
} from "../../lib/users";
import "../../app/auth.css";
import "./users.css";

type Kind = "staff" | "student";

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "Never";

/** Staff screen (English). Permissions: users.read to view; creating/changing depends on the account kind. */
export default function UsersPage() {
  const { data: me } = useMe();
  const [filter, setFilter] = useState<"" | Kind>("");
  const users = useUsers(filter || undefined);
  const roles = useRoles();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [resetting, setResetting] = useState<User | null>(null);
  const [resettingMfa, setResettingMfa] = useState<User | null>(null);
  const [tempPassword, setTempPassword] = useState<{ name: string; identifier: string; password: string } | null>(null);
  const reset = useResetPassword();
  const unlock = useUnlockUser();
  const resetMfa = useResetTwoStep();

  const canCreateStaff = hasPermission(me, "users.create.staff");
  const canCreateStudent = hasPermission(me, "users.create.student");
  const canManageRoles = hasPermission(me, "users.roles.manage");
  const canManage = (u: User) => (u.kind === "student" ? canCreateStudent || canManageRoles : canManageRoles);
  const canReset = (u: User) => hasPermission(me, u.kind === "student" ? "users.reset_password.student" : "users.reset_password.staff");

  const columns: Column<User>[] = [
    {
      key: "name",
      header: "Name",
      render: (u) => (
        <div className="user-cell">
          <span className="user-name">{u.name}</span>
          <span className="user-sub">{u.kind === "student" ? `PRN ${u.prn}` : u.email}</span>
        </div>
      ),
      searchText: (u) => `${u.name} ${u.email ?? ""} ${u.prn ?? ""} ${u.phone ?? ""}`,
    },
    { key: "roles", header: "Roles", render: (u) => u.role_labels.join(", "), searchText: (u) => u.role_labels.join(" ") },
    {
      key: "status",
      header: "Status",
      render: (u) => (
        <div className="badge-row">
          {u.status === "disabled" ? <StatusBadge tone="danger">Disabled</StatusBadge> : <StatusBadge tone="success">Active</StatusBadge>}
          {u.locked && <StatusBadge tone="warning">Locked</StatusBadge>}
          {u.must_change_password && <StatusBadge tone="info">Temporary password</StatusBadge>}
        </div>
      ),
    },
    {
      key: "mfa",
      header: "2-step",
      render: (u) =>
        u.mfa_enabled ? <StatusBadge tone="success">On</StatusBadge> : u.mfa_required ? <StatusBadge tone="warning">Required, not set up</StatusBadge> : <span className="muted">Off</span>,
    },
    { key: "last", header: "Last sign-in", render: (u) => <span className="nowrap">{fmtDate(u.last_login_at)}</span> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (u) => (
        <div className="row-actions">
          {u.locked && canManage(u) && (
            <button type="button" className="link-btn" onClick={() => unlock.mutate(u.id)}>
              Unlock
            </button>
          )}
          {canManage(u) && (
            <button type="button" className="link-btn" onClick={() => setEditing(u)}>
              Edit
            </button>
          )}
          {canReset(u) && u.id !== me?.id && (
            <button type="button" className="link-btn" onClick={() => setResetting(u)}>
              Reset password
            </button>
          )}
          {canReset(u) && u.mfa_enabled && u.id !== me?.id && (
            <button type="button" className="link-btn" onClick={() => setResettingMfa(u)}>
              Reset 2-step
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Administration</div>
          <h1>Users</h1>
        </div>
        {canCreateStaff && (
          <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
            Add user
          </button>
        )}
      </div>

      <div className="seg filter-seg" role="group" aria-label="Account type">
        {(
          [
            ["", "All"],
            ["staff", "Staff"],
            ["student", "Students"],
          ] as const
        ).map(([value, label]) => (
          <button key={label} type="button" className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>
            {label}
          </button>
        ))}
      </div>

      {users.error && <p className="form-error">{users.error.message}</p>}
      {users.isLoading ? (
        <p className="muted">Loading…</p>
      ) : (
        <DataTable columns={columns} rows={users.data?.items ?? []} rowKey={(u) => u.id} searchPlaceholder="Search by name, email, PRN or phone" emptyTitle="No accounts found" />
      )}

      <AddUserModal
        open={adding}
        onClose={() => setAdding(false)}
        roles={roles.data ?? []}
        allowedKinds={canCreateStaff ? ["staff"] : []}
        onCreated={(user, password) => {
          setAdding(false);
          setTempPassword({ name: user.name, identifier: user.kind === "student" ? `PRN ${user.prn}` : user.email ?? "", password });
        }}
      />

      {editing && <EditUserModal user={editing} roles={roles.data ?? []} canManageRoles={canManageRoles} isSelf={editing.id === me?.id} onClose={() => setEditing(null)} />}

      <ConfirmDialog
        open={resetting !== null}
        title={`Reset password for ${resetting?.name ?? ""}?`}
        message="They will be signed out everywhere and must choose a new password with the temporary one you give them."
        confirmLabel="Reset password"
        requireReason
        danger
        onCancel={() => setResetting(null)}
        onConfirm={(reason) => {
          const user = resetting!;
          setResetting(null);
          reset.mutate(
            { id: user.id, reason },
            { onSuccess: (r) => setTempPassword({ name: user.name, identifier: user.kind === "student" ? `PRN ${user.prn}` : user.email ?? "", password: r.temporary_password }) },
          );
        }}
      />

      <ConfirmDialog
        open={resettingMfa !== null}
        title={`Reset 2-step verification for ${resettingMfa?.name ?? ""}?`}
        message="Only for a lost phone with no recovery codes: confirm who they are first. They will be signed out everywhere and must set up 2-step verification again at their next sign-in."
        confirmLabel="Reset 2-step"
        requireReason
        danger
        onCancel={() => setResettingMfa(null)}
        onConfirm={(reason) => {
          const user = resettingMfa!;
          setResettingMfa(null);
          resetMfa.mutate({ id: user.id, reason });
        }}
      />

      <Modal open={tempPassword !== null} title="Temporary password" onClose={() => setTempPassword(null)}>
        {tempPassword && (
          <>
            <p className="muted">
              Give this to <b>{tempPassword.name}</b> ({tempPassword.identifier}). It is shown only once. They must choose their own password when they first sign in.
            </p>
            <div className="temp-password" aria-label="Temporary password">
              {tempPassword.password}
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => navigator.clipboard?.writeText(tempPassword.password)}>
                Copy
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setTempPassword(null)}>
                Done
              </button>
            </div>
          </>
        )}
      </Modal>
    </>
  );
}

function RoleChecklist({ roles, value, onChange }: { roles: RoleInfo[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <fieldset className="role-list">
      <legend>Roles</legend>
      {roles.map((r) => (
        <label key={r.id} className="role-option">
          <input
            type="checkbox"
            checked={value.includes(r.id)}
            onChange={(e) => onChange(e.target.checked ? [...value, r.id] : value.filter((x) => x !== r.id))}
          />
          <span>{r.label}</span>
          {r.mfa_required && <span className="role-mfa">2-step required</span>}
        </label>
      ))}
    </fieldset>
  );
}

function FieldError({ error, field }: { error: unknown; field: string }) {
  if (!(error instanceof ApiError) || error.field !== field) return null;
  return <span className="field-error">{error.message}</span>;
}

function AddUserModal({
  open,
  onClose,
  roles,
  allowedKinds,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  roles: RoleInfo[];
  allowedKinds: Kind[];
  onCreated: (user: User, temporaryPassword: string) => void;
}) {
  const empty: NewUser = { kind: allowedKinds[0] ?? "student", name: "", email: "", prn: "", phone: "", roles: [] };
  const [form, setForm] = useState<NewUser>(empty);
  const create = useCreateUser();
  const close = () => {
    setForm(empty);
    create.reset();
    onClose();
  };
  const err = create.error;
  const generalError = err instanceof ApiError && !err.field ? err.message : null;

  return (
    <Modal open={open} title="Add user" onClose={close} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const body: NewUser = {
            kind: form.kind,
            name: form.name.trim(),
            phone: form.phone?.trim() || undefined,
            roles: form.kind === "staff" ? form.roles : [],
            ...(form.kind === "staff" ? { email: form.email?.trim() } : { prn: form.prn?.trim() }),
          };
          create.mutate(body, { onSuccess: (r) => (setForm(empty), onCreated(r.user, r.temporary_password)) });
        }}
      >
        {allowedKinds.length > 1 && (
          <div className="auth-tabs" role="tablist">
            {allowedKinds.map((k) => (
              <button key={k} type="button" role="tab" aria-selected={form.kind === k} className={form.kind === k ? "active" : ""} onClick={() => setForm({ ...form, kind: k })}>
                {k === "staff" ? "Staff" : "Student"}
              </button>
            ))}
          </div>
        )}
        {generalError && <div className="form-error">{generalError}</div>}
        <div className="field">
          <label htmlFor="u-name">Full name</label>
          <input id="u-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <FieldError error={err} field="name" />
        </div>
        {form.kind === "staff" ? (
          <div className="field">
            <label htmlFor="u-email">Email (used to sign in)</label>
            <input id="u-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            <FieldError error={err} field="email" />
          </div>
        ) : (
          <div className="field">
            <label htmlFor="u-prn">PRN (used to sign in)</label>
            <input id="u-prn" value={form.prn} onChange={(e) => setForm({ ...form, prn: e.target.value.toUpperCase() })} required />
            <FieldError error={err} field="prn" />
          </div>
        )}
        <div className="field">
          <label htmlFor="u-phone">Mobile (optional)</label>
          <input id="u-phone" type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        </div>
        {form.kind === "staff" && <RoleChecklist roles={roles} value={form.roles} onChange={(r) => setForm({ ...form, roles: r })} />}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={close}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={create.isPending || !form.name.trim() || (form.kind === "staff" && form.roles.length === 0)}>
            {create.isPending ? "Creating…" : "Create account"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function EditUserModal({
  user,
  roles,
  canManageRoles,
  isSelf,
  onClose,
}: {
  user: User;
  roles: RoleInfo[];
  canManageRoles: boolean;
  isSelf: boolean;
  onClose: () => void;
}) {
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email ?? "");
  const [phone, setPhone] = useState(user.phone ?? "");
  const [selected, setSelected] = useState(user.roles);
  const [status, setStatus] = useState(user.status);
  const [reason, setReason] = useState("");
  const update = useUpdateUser();
  const disabling = status === "disabled" && user.status !== "disabled";
  const generalError = update.error instanceof ApiError && !update.error.field ? update.error.message : null;

  return (
    <Modal open title={`Edit ${user.name}`} onClose={onClose} wide>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(
            {
              id: user.id,
              changes: {
                // A student's name and contact details live in their student record.
                ...(user.kind === "staff" ? { name: name.trim(), phone: phone.trim() } : {}),
                ...(user.kind === "staff" && email.trim() ? { email: email.trim() } : {}),
                ...(user.kind === "staff" && canManageRoles ? { roles: selected } : {}),
                status,
                reason: reason.trim() || undefined,
              },
            },
            { onSuccess: onClose },
          );
        }}
      >
        {generalError && <div className="form-error">{generalError}</div>}
        {user.kind === "student" && (
          <p className="muted">
            Name and contact details are edited in the <Link to="/app/students">student's record</Link>. Here you can only turn the login on or off.
          </p>
        )}
        {user.kind === "staff" && (
          <div className="field">
            <label htmlFor="e-name">Full name</label>
            <input id="e-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
        )}
        {user.kind === "staff" && (
          <div className="field">
            <label htmlFor="e-email">Email</label>
            <input id="e-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <FieldError error={update.error} field="email" />
          </div>
        )}
        {user.kind === "staff" && (
          <div className="field">
            <label htmlFor="e-phone">Mobile</label>
            <input id="e-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
        )}
        {user.kind === "staff" && canManageRoles && (
          <>
            <RoleChecklist roles={roles} value={selected} onChange={setSelected} />
            <FieldError error={update.error} field="roles" />
          </>
        )}
        {!isSelf && (
          <div className="field">
            <label htmlFor="e-status">Account</label>
            <select id="e-status" value={status} onChange={(e) => setStatus(e.target.value as User["status"])}>
              <option value="active">Active</option>
              <option value="disabled">Disabled (cannot sign in)</option>
            </select>
            <FieldError error={update.error} field="status" />
          </div>
        )}
        <div className="field">
          <label htmlFor="e-reason">Reason {disabling ? "(required)" : "(optional)"} — recorded in the audit log</label>
          <input id="e-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={update.isPending || (disabling && reason.trim().length < 5)}>
            {update.isPending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

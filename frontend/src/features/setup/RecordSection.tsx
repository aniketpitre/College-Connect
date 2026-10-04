import { useState } from "react";
import { DataTable, type Column } from "../../components/DataTable";
import { Modal } from "../../components/Modal";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError } from "../../lib/api";
import { useSaveRecord, type RecordStatus } from "../../lib/setup";

export interface FieldDef {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "select" | "list";
  options?: { value: string; label: string }[];
  required?: boolean;
  /** Editable after creation (codes and links usually are not). */
  editable?: boolean;
  hint?: string;
}

interface Props<T extends { id: string; status: RecordStatus }> {
  title: string;
  path: string;
  rows: T[];
  columns: Column<T>[];
  fields: FieldDef[];
  canManage: boolean;
  /** Values for a new record (e.g. the programme the list is filtered to). */
  defaults?: Record<string, unknown>;
  extraActions?: (row: T) => React.ReactNode;
}

type Values = Record<string, string>;

const toValues = (fields: FieldDef[], source: Record<string, unknown>): Values =>
  Object.fromEntries(
    fields.map((f) => {
      const v = source[f.name];
      return [f.name, v === null || v === undefined ? "" : Array.isArray(v) ? v.join(", ") : String(v)];
    }),
  );

function toBody(fields: FieldDef[], values: Values, only?: (f: FieldDef) => boolean) {
  const body: Record<string, unknown> = {};
  for (const f of fields) {
    if (only && !only(f)) continue;
    const raw = values[f.name]?.trim() ?? "";
    if (f.type === "number") body[f.name] = raw === "" ? null : Number(raw);
    else if (f.type === "list") body[f.name] = raw ? raw.split(",").map((x) => x.trim()).filter(Boolean) : [];
    else if (raw !== "" || f.required) body[f.name] = raw;
  }
  return body;
}

/** A list of one kind of setup record, with add / edit / archive for those allowed to manage it. */
export function RecordSection<T extends { id: string; status: RecordStatus }>({
  title,
  path,
  rows,
  columns,
  fields,
  canManage,
  defaults = {},
  extraActions,
}: Props<T>) {
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<T | "new" | null>(null);
  const [values, setValues] = useState<Values>({});
  const save = useSaveRecord(path);
  const visible = rows.filter((r) => showArchived || r.status === "active");
  const archivedCount = rows.length - rows.filter((r) => r.status === "active").length;
  const err = save.error instanceof ApiError ? save.error : null;
  const isNew = editing === "new";

  const open = (row: T | "new") => {
    save.reset();
    setValues(toValues(fields, row === "new" ? defaults : (row as unknown as Record<string, unknown>)));
    setEditing(row);
  };

  const allColumns: Column<T>[] = [
    ...columns,
    {
      key: "_status",
      header: "",
      render: (r) => (r.status === "archived" ? <StatusBadge>Archived</StatusBadge> : null),
    },
    {
      key: "_actions",
      header: "",
      align: "right",
      render: (r) => (
        <div className="row-actions">
          {extraActions?.(r)}
          {canManage && fields.some((f) => f.editable) && (
            <button type="button" className="link-btn" onClick={() => open(r)}>
              Edit
            </button>
          )}
          {canManage && (
            <button
              type="button"
              className="link-btn"
              disabled={save.isPending}
              onClick={() => save.mutate({ id: r.id, body: { status: r.status === "active" ? "archived" : "active" } })}
            >
              {r.status === "active" ? "Archive" : "Restore"}
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <section className="setup-section">
      <div className="section-head">
        <h2>{title}</h2>
        <div className="row-actions">
          {archivedCount > 0 && (
            <label className="muted check-label">
              <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Show archived ({archivedCount})
            </label>
          )}
          {canManage && (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => open("new")}>
              Add
            </button>
          )}
        </div>
      </div>
      {save.error && !editing && <p className="form-error">{save.error.message}</p>}
      <DataTable columns={allColumns} rows={visible} rowKey={(r) => r.id} emptyTitle={`No ${title.toLowerCase()} yet`} pageSize={50} />

      <Modal open={editing !== null} title={isNew ? `Add ${title.toLowerCase().replace(/s$/, "")}` : `Edit`} onClose={() => setEditing(null)}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const body = isNew ? { ...toBody(fields, values), ...pickHidden(defaults, fields) } : toBody(fields, values, (f) => !!f.editable);
            save.mutate({ id: isNew ? undefined : (editing as T).id, body }, { onSuccess: () => setEditing(null) });
          }}
        >
          {err && !err.field && <div className="form-error">{err.message}</div>}
          {fields
            .filter((f) => isNew || f.editable)
            .map((f) => (
              <div className="field" key={f.name}>
                <label htmlFor={`f-${f.name}`}>{f.label}</label>
                {f.type === "select" ? (
                  <select id={`f-${f.name}`} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} required={f.required}>
                    <option value="">Choose…</option>
                    {f.options?.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    id={`f-${f.name}`}
                    type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                    value={values[f.name] ?? ""}
                    onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                    required={f.required}
                  />
                )}
                {f.hint && <span className="field-hint">{f.hint}</span>}
                {err?.field === f.name && <span className="field-error">{err.message}</span>}
              </div>
            ))}
          {err?.field && !fields.some((f) => f.name === err.field && (isNew || f.editable)) && <div className="form-error">{err.message}</div>}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </Modal>
    </section>
  );
}

/** Defaults for fields not shown in the form (e.g. programme_id when the list is filtered). */
function pickHidden(defaults: Record<string, unknown>, fields: FieldDef[]) {
  return Object.fromEntries(Object.entries(defaults).filter(([k]) => !fields.some((f) => f.name === k)));
}

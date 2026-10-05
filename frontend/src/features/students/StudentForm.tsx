import { STUDENT_STRINGS } from "../../i18n/student";
import { ApiError } from "../../lib/api";
import type { SetupOverview } from "../../lib/setup";

const L = STUDENT_STRINGS.en;
import type { Values } from "./studentValues";

interface Props {
  setup: SetupOverview;
  values: Values;
  onChange: (v: Values) => void;
  error: unknown;
  isNew: boolean;
}

/** Office form for a student record (English, staff screen). */
export function StudentFields({ setup, values, onChange, error, isNew }: Props) {
  const err = error instanceof ApiError ? error : null;
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const next = { ...values, [k]: e.target.value };
    if (k === "programme_id" || k === "year_of_study") next.division_id = "";
    onChange(next);
  };
  const programme = setup.programmes.find((p) => p.id === values.programme_id);
  const divisions = setup.divisions.filter(
    (d) => d.status === "active" && d.programme_id === values.programme_id && String(d.year_of_study) === values.year_of_study,
  );

  const field = (k: string, opts: { type?: string; required?: boolean; hint?: string; label?: string } = {}) => (
    <div className="field" key={k}>
      <label htmlFor={`s-${k}`}>{opts.label ?? L.fields[k]}</label>
      <input id={`s-${k}`} type={opts.type ?? "text"} value={values[k] ?? ""} onChange={set(k)} required={opts.required} />
      {opts.hint && <span className="field-hint">{opts.hint}</span>}
      {(err?.field === k || err?.field === k.split(".")[0]) && <span className="field-error">{err.message}</span>}
    </div>
  );
  const select = (k: string, options: { value: string; label: string }[], required = false) => (
    <div className="field" key={k}>
      <label htmlFor={`s-${k}`}>{L.fields[k]}</label>
      <select id={`s-${k}`} value={values[k] ?? ""} onChange={set(k)} required={required}>
        <option value="">{required ? "Choose…" : "—"}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {err?.field === k && <span className="field-error">{err.message}</span>}
    </div>
  );

  return (
    <>
      {err && !err.field && <div className="form-error">{err.message}</div>}
      <h3 className="form-section">{L.sections.academic}</h3>
      <div className="field-row">
        {isNew && field("prn", { required: true, hint: "The student signs in with this" })}
        {select("programme_id", setup.programmes.filter((p) => p.status === "active").map((p) => ({ value: p.id, label: `${p.code} · ${p.name}` })), true)}
        {select("year_of_study", (programme?.year_labels ?? []).map((label, i) => ({ value: String(i + 1), label })), true)}
        {select("division_id", divisions.map((d) => ({ value: d.id, label: d.name })))}
        {field("roll_no")}
        {field("batch", { hint: "Practical batch, e.g. B1" })}
        {field("admission_date", { type: "date" })}
        {!isNew && select("status", Object.entries(L.studentStatus).map(([value, label]) => ({ value, label })), true)}
      </div>
      <h3 className="form-section">{L.sections.personal}</h3>
      <div className="field-row">
        {field("name", { required: true })}
        {field("mother_name")}
        {select("gender", Object.entries(L.genders).map(([value, label]) => ({ value, label })))}
        {field("dob", { type: "date" })}
        {select("category_id", setup.categories.filter((c) => c.status === "active").map((c) => ({ value: c.id, label: `${c.code} · ${c.name}` })))}
        {field("aadhaar", { hint: isNew || !values.aadhaar ? "12 digits; only the last 4 are kept" : undefined })}
        {field("apaar_id")}
      </div>
      <h3 className="form-section">{L.sections.contact}</h3>
      <div className="field-row">
        {field("phone", { type: "tel" })}
        {field("email", { type: "email" })}
        {field("address.line")}
        {field("address.city")}
        {field("address.district")}
        {field("address.state")}
        {field("address.pincode")}
      </div>
      <h3 className="form-section">{L.sections.guardian}</h3>
      <div className="field-row">
        {field("guardian.name")}
        {field("guardian.relation")}
        {field("guardian.phone", { type: "tel" })}
        {field("guardian.email", { type: "email" })}
      </div>
      <label className="check-label consent-check">
        <input type="checkbox" checked={values.guardian_consent === "yes"} onChange={(e) => onChange({ ...values, guardian_consent: e.target.checked ? "yes" : "" })} />
        Parent/guardian consent recorded (needed for students under 18)
      </label>
      <h3 className="form-section">{L.sections.education}</h3>
      <div className="field-row">
        {field("previous_education.exam", { hint: "e.g. HSC" })}
        {field("previous_education.board")}
        {field("previous_education.year", { type: "number" })}
        {field("previous_education.percentage", { type: "number" })}
      </div>
    </>
  );
}

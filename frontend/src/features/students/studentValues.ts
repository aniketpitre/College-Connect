import type { Student } from "../../lib/students";

export type Values = Record<string, string>;

const NESTED = ["address", "guardian", "previous_education"] as const;
const NUMBER_FIELDS = new Set(["year_of_study", "previous_education.year", "previous_education.percentage"]);

/** A student record → flat form values ("guardian.name": "…"). */
export function toValues(s?: Partial<Student>): Values {
  const v: Values = {};
  const flat = (key: string, value: unknown) => (v[key] = value === null || value === undefined ? "" : String(value));
  for (const key of ["name", "prn", "mother_name", "gender", "dob", "email", "phone", "category_id", "apaar_id", "programme_id", "year_of_study", "division_id", "roll_no", "batch", "admission_date", "status"] as const)
    flat(key, s?.[key]);
  for (const group of NESTED) {
    const obj = (s?.[group] ?? {}) as Record<string, unknown>;
    for (const [k, value] of Object.entries(obj)) flat(`${group}.${k}`, value);
  }
  if (!v["address.state"]) v["address.state"] = "Maharashtra";
  v.guardian_consent = s?.guardian_consent ? "yes" : "";
  return v;
}

/** Flat form values → API body (nested objects, numbers, empty strings dropped). */
export function toBody(values: Values, changedOnly?: Values): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  const value = (k: string) => {
    const raw = (values[k] ?? "").trim();
    if (raw === "") return null;
    return NUMBER_FIELDS.has(k) ? Number(raw) : raw;
  };
  for (const k of Object.keys(values)) {
    if (k.includes(".") || k === "guardian_consent") continue;
    if (changedOnly && values[k] === changedOnly[k]) continue;
    const v = value(k);
    if (v !== null || changedOnly) body[k] = v;
  }
  for (const group of NESTED) {
    const keys = Object.keys(values).filter((k) => k.startsWith(`${group}.`));
    if (changedOnly && keys.every((k) => values[k] === changedOnly[k])) continue;
    const obj: Record<string, unknown> = {};
    for (const k of keys) {
      const v = value(k);
      if (v !== null) obj[k.slice(group.length + 1)] = v;
    }
    if (Object.keys(obj).length || changedOnly) body[group] = obj;
  }
  if (!changedOnly || values.guardian_consent !== changedOnly.guardian_consent) body.guardian_consent = values.guardian_consent === "yes";
  return body;
}

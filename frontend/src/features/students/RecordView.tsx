import { STUDENT_STRINGS } from "../../i18n/student";
import type { Student } from "../../lib/students";

/** The record laid out in sections; used by the office and by the student (in their language). */
export function RecordView({ s, lang = "en" }: { s: Student; lang?: "en" | "hi" | "mr" }) {
  const T = STUDENT_STRINGS[lang];
  const fmt = (iso: string | null) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(lang === "en" ? "en-IN" : `${lang}-IN`, { day: "numeric", month: "long", year: "numeric" }) : T.notSet);
  const row = (label: string, value: React.ReactNode) => (
    <div className="dl-row" key={label}>
      <dt>{label}</dt>
      <dd>{value || T.notSet}</dd>
    </div>
  );
  const nested = (group: "address" | "guardian" | "previous_education", keys: string[]) =>
    keys.map((k) => row(T.fields[`${group}.${k}`], (s[group] as Record<string, unknown> | null)?.[k] as string));
  return (
    <div className="record-grid">
      <section className="card">
        <h2>{T.sections.personal}</h2>
        <dl>
          {row(T.fields.name, s.name)}
          {row(T.fields.mother_name, s.mother_name)}
          {row(T.fields.gender, s.gender ? T.genders[s.gender] : null)}
          {row(T.fields.dob, fmt(s.dob))}
          {row(T.fields.category_id, s.category_code ? `${s.category_code} · ${s.category_name}` : null)}
          {row(T.fields.aadhaar, s.aadhaar_masked)}
          {row(T.fields.apaar_id, s.apaar_id)}
        </dl>
      </section>
      <section className="card">
        <h2>{T.sections.academic}</h2>
        <dl>
          {row(T.fields.prn, s.prn)}
          {row(T.fields.programme_id, s.programme_name ? `${s.programme_code} · ${s.programme_name}` : s.programme_code)}
          {row(T.fields.year_of_study, s.year_label)}
          {row(T.fields.division_id, s.division)}
          {row(T.fields.roll_no, s.roll_no)}
          {row(T.fields.admission_date, fmt(s.admission_date))}
          {row(T.fields.status, T.studentStatus[s.status])}
        </dl>
      </section>
      <section className="card">
        <h2>{T.sections.contact}</h2>
        <dl>
          {row(T.fields.phone, s.phone)}
          {row(T.fields.email, s.email)}
          {nested("address", ["line", "city", "district", "state", "pincode"])}
        </dl>
      </section>
      <section className="card">
        <h2>{T.sections.guardian}</h2>
        <dl>{nested("guardian", ["name", "relation", "phone", "email"])}</dl>
        <h2>{T.sections.education}</h2>
        <dl>{nested("previous_education", ["exam", "board", "year", "percentage"])}</dl>
      </section>
    </div>
  );
}

import { STUDENT_STRINGS } from "../../i18n/student";
import type { SetupOverview } from "../../lib/setup";

/** A stored value as people read it ("OBC", "Pune, Maharashtra 411001", "Male"). */
export function describeValue(field: string, value: unknown, setup?: SetupOverview, lang: "en" | "hi" | "mr" = "en"): string {
  const L = STUDENT_STRINGS[lang];
  if (value === null || value === undefined || value === "") return "—";
  if (field === "category_id") {
    const c = setup?.categories.find((x) => x.id === value);
    return c ? `${c.code} · ${c.name}` : String(value);
  }
  if (field === "gender") return L.genders[String(value)] ?? String(value);
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== null && v !== "")
      .map(([k, v]) => `${L.fields[`${field}.${k}`] ?? k}: ${v}`)
      .join(", ") || "—";
  }
  return String(value);
}

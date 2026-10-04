import type { Language } from "../lib/types";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हि" },
  { code: "mr", label: "मर" },
];

export default function LanguageToggle({ value, onChange }: { value: Language; onChange: (l: Language) => void }) {
  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      {LANGUAGES.map((l) => (
        <button key={l.code} type="button" className={l.code === value ? "active" : ""} aria-pressed={l.code === value} onClick={() => onChange(l.code)}>
          {l.label}
        </button>
      ))}
    </div>
  );
}

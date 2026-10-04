import type { Language } from "../../lib/types";

type Strings = Record<Language, { title: string; body: string; back: string }>;

// Temporary public pages; Phase 1 replaces them with sign-in and real verification.
export const VERIFY: Strings = {
  en: { title: "Verify a document", body: "Receipt and certificate verification is coming soon.", back: "Back to the help desk" },
  hi: { title: "दस्तावेज़ सत्यापित करें", body: "रसीद और प्रमाणपत्र सत्यापन जल्द आ रहा है।", back: "हेल्प डेस्क पर वापस जाएं" },
  mr: { title: "दस्तऐवज पडताळा", body: "पावती आणि प्रमाणपत्र पडताळणी लवकरच येत आहे.", back: "हेल्प डेस्कवर परत जा" },
};

export const NOT_FOUND: Strings = {
  en: { title: "Page not found", body: "This address doesn't exist.", back: "Go to the help desk" },
  hi: { title: "पेज नहीं मिला", body: "यह पता मौजूद नहीं है।", back: "हेल्प डेस्क पर जाएं" },
  mr: { title: "पान सापडले नाही", body: "हा पत्ता अस्तित्वात नाही.", back: "हेल्प डेस्कवर जा" },
};

export function browserLanguage(): Language {
  const lang = (typeof navigator !== "undefined" ? navigator.language : "en").slice(0, 2);
  return lang === "hi" || lang === "mr" ? lang : "en";
}

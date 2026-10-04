import type { Language } from "./types";

const KEY = "cc-lang";

export function savedLanguage(): Language {
  try {
    const value = localStorage.getItem(KEY);
    if (value === "en" || value === "hi" || value === "mr") return value;
  } catch {
    // storage unavailable (private mode)
  }
  const browser = (typeof navigator !== "undefined" ? navigator.language : "en").slice(0, 2);
  return browser === "hi" || browser === "mr" ? browser : "en";
}

export function saveLanguage(language: Language) {
  try {
    localStorage.setItem(KEY, language);
  } catch {
    // ignore
  }
}

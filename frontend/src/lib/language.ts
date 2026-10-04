import { useSyncExternalStore } from "react";
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

const listeners = new Set<() => void>();
let current: Language | null = null;

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot(): Language {
  current ??= savedLanguage();
  return current;
}

/** Switch the language everywhere (and remember it on this device). */
export function chooseLanguage(l: Language) {
  current = l;
  saveLanguage(l);
  listeners.forEach((fn) => fn());
}

/** The page language, remembered across visits and shared by every screen (changing it anywhere updates all). */
export function useLanguage(): [Language, (l: Language) => void] {
  const language = useSyncExternalStore(subscribe, snapshot, snapshot);
  return [language, chooseLanguage];
}

/** Tests start each case from the saved setting. */
export function resetLanguageForTests() {
  current = null;
}

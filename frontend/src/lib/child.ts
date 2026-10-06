import { useSyncExternalStore } from "react";

/** Parents: the child the portal is showing. Sent to the API as the X-Child header. */
const KEY = "cc-child";
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

let current: string | null = read();

export function childId(): string | null {
  return current;
}

export function setChild(id: string | null) {
  current = id;
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    // private mode: the choice lasts until the page is closed
  }
  listeners.forEach((l) => l());
}

export function useChildId(): string | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
  );
}

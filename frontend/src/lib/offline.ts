/**
 * Data kept on this device for offline attendance (plan 2.3), in IndexedDB:
 * - "cache": the latest copy of the teacher's day and of each class list they opened;
 * - "outbox": attendance saved while offline, sent when the connection is back.
 * Falls back to memory where IndexedDB isn't available (private windows, tests).
 */

const DB_NAME = "collegeconnect";
const STORES = ["cache", "outbox"] as const;
type Store = (typeof STORES)[number];

const memory: Record<Store, Map<string, unknown>> = { cache: new Map(), outbox: new Map() };
let dbPromise: Promise<IDBDatabase | null> | null = null;

function openDb(): Promise<IDBDatabase | null> {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    try {
      if (typeof indexedDB === "undefined") return resolve(null);
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => STORES.forEach((s) => req.result.objectStoreNames.contains(s) || req.result.createObjectStore(s));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return dbPromise;
}

async function run<T>(store: Store, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T | undefined> {
  const db = await openDb();
  if (!db) return undefined;
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(store, mode).objectStore(store));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function put(store: Store, key: string, value: unknown): Promise<void> {
  if (!(await openDb())) return void memory[store].set(key, value);
  await run(store, "readwrite", (s) => s.put(value, key));
}

export async function get<T>(store: Store, key: string): Promise<T | undefined> {
  if (!(await openDb())) return memory[store].get(key) as T | undefined;
  return (await run(store, "readonly", (s) => s.get(key))) as T | undefined;
}

export async function remove(store: Store, key: string): Promise<void> {
  if (!(await openDb())) return void memory[store].delete(key);
  await run(store, "readwrite", (s) => s.delete(key));
}

export async function all<T>(store: Store): Promise<T[]> {
  if (!(await openDb())) return [...memory[store].values()] as T[];
  return ((await run(store, "readonly", (s) => s.getAll())) ?? []) as T[];
}

/** For tests: forget everything kept in memory. */
export function resetOfflineForTests() {
  memory.cache.clear();
  memory.outbox.clear();
}

export function registerServiceWorker() {
  if (import.meta.env.PROD && "serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => undefined));
  }
}

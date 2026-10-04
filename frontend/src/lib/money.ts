const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

/** Formats an amount stored as integer paise, e.g. 12500000 → "₹1,25,000.00". */
export function formatPaise(paise: number): string {
  if (!Number.isInteger(paise)) throw new Error(`Money must be integer paise, got ${paise}`);
  return INR.format(paise / 100);
}

/** "12,500.50" (rupees, as typed) → 1250050 paise; null if it isn't a valid amount. No floating point. */
export function parseRupees(text: string): number | null {
  const clean = text.replace(/[,\s₹]/g, "").replace(/^Rs\.?/i, "");
  const m = /^(\d{1,12})(?:\.(\d{1,2}))?$/.exec(clean);
  if (!m) return null;
  return Number(m[1]) * 100 + Number((m[2] ?? "").padEnd(2, "0"));
}

/** 1250050 → "12500.50" for an input box (no grouping, so it parses back exactly). */
export function paiseToInput(paise: number): string {
  const rupees = Math.trunc(paise / 100);
  const rest = Math.abs(paise % 100);
  return rest ? `${rupees}.${String(rest).padStart(2, "0")}` : String(rupees);
}

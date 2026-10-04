const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

/** Formats an amount stored as integer paise, e.g. 12500000 → "₹1,25,000.00". */
export function formatPaise(paise: number): string {
  if (!Number.isInteger(paise)) throw new Error(`Money must be integer paise, got ${paise}`);
  return INR.format(paise / 100);
}

import { formatPaise } from "../lib/money";

export function MoneyText({ paise, className }: { paise: number; className?: string }) {
  return <span className={["money", paise < 0 ? "negative" : "", className].filter(Boolean).join(" ")}>{formatPaise(paise)}</span>;
}

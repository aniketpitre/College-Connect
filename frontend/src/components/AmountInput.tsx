import { parseRupees } from "../lib/money";

interface Props {
  id: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  label?: string;
}

/** A rupee amount typed as text (parsed to paise exactly with parseRupees). */
export function AmountInput({ id, value, onChange, required, label }: Props) {
  const invalid = value.trim() !== "" && parseRupees(value) === null;
  return (
    <span className="amount-input">
      <span aria-hidden="true">₹</span>
      <input
        id={id}
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={invalid || undefined}
        aria-label={label}
        required={required}
        placeholder="0"
      />
    </span>
  );
}

import { useState } from "react";

interface Props {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  showLabel: string;
  hideLabel: string;
  invalid?: boolean;
}

export default function PasswordInput({ id, value, onChange, autoComplete, showLabel, hideLabel, invalid }: Props) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="password-wrap">
      <input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        aria-invalid={invalid || undefined}
        required
      />
      <button type="button" className="password-toggle" onClick={() => setVisible((v) => !v)} aria-controls={id}>
        {visible ? hideLabel : showLabel}
      </button>
    </div>
  );
}

export type Tone = "neutral" | "success" | "warning" | "danger" | "info";

/** A small status label. Always pass text: colour alone never carries the meaning. */
export function StatusBadge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return <span className={`status-badge tone-${tone}`}>{children}</span>;
}

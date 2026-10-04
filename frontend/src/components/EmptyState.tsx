export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="empty-state" role="status">
      <p className="empty-state-title">{title}</p>
      {children && <div className="empty-state-body">{children}</div>}
    </div>
  );
}

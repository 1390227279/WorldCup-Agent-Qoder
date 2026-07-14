interface Props {
  label: string;
  value: string;
  note?: string;
  accent?: boolean;
}

export default function MetricCard({ label, value, note, accent = false }: Props) {
  return (
    <div className={`dashboard-card border-l-2 p-4 ${accent ? "border-l-[var(--color-primary)]" : "border-l-[var(--color-border)]"}`}>
      <p className="dashboard-label uppercase">{label}</p>
      <p className={`mt-2 font-mono text-2xl font-semibold ${accent ? "text-[var(--color-primary)]" : "text-white"}`}>{value}</p>
      {note && <p className="mt-1 text-xs text-[var(--color-text-muted)]">{note}</p>}
    </div>
  );
}

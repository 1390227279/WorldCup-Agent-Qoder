import type { Event } from "../types";
import { resolveImpactMode } from "../utils/eventImpact";

export default function EventImpactBadge({ event }: { event: Event }) {
  const mode = resolveImpactMode(event);
  if (mode === "MATH") {
    return <span className="inline-flex rounded-md border border-[var(--color-primary)] bg-[var(--color-primary)]/10 px-2 py-0.5 text-[11px] font-semibold text-[var(--color-primary)] shadow-[0_0_8px_rgba(230,183,16,0.14)]">∑ 数学影响</span>;
  }
  if (mode === "INVALID") {
    return <span className="inline-flex rounded-md border border-[var(--color-error)]/40 bg-[var(--color-error)]/10 px-2 py-0.5 text-[11px] text-[var(--color-error)]">数据无效</span>;
  }
  return <span title="仅作为 AI 解读背景，不影响数学胜率" className="inline-flex rounded-md border border-dashed border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-text-muted)]">✦ AI 解读</span>;
}

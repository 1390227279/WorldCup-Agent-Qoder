import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { Event, Team } from "../types";

interface ScenarioSliderProps {
  selectedEventIds: number[];
  onChange: (ids: number[]) => void | Promise<void>;
  disabled?: boolean;
}

const PAGE_SIZE = 20;
const SEVERITY_LABELS: Record<string, string> = {
  CRITICAL: "严重",
  MAJOR: "重要",
  MINOR: "一般",
};

function ImpactModeBadge({ event }: { event: Event }) {
  const isMath = event.impact_mode === "MATH";
  const tooltip = isMath
    ? "此事件会修正进球期望，并改变比赛胜率与晋级概率"
    : "此事件仅作为 AI 解读背景，不影响数学胜率模型";
  return (
    <span className="group relative inline-flex shrink-0" tabIndex={0} aria-label={tooltip}>
      <span className={isMath
        ? "rounded-full border border-[var(--color-gold)] bg-[var(--color-gold)]/20 px-2 py-0.5 text-[10px] font-semibold text-[var(--color-gold)] shadow-[0_0_12px_rgba(230,183,16,0.25)]"
        : "rounded-full border border-dashed border-[var(--color-border)] bg-transparent px-2 py-0.5 text-[10px] text-[var(--color-text-muted)]"
      }>
        {isMath ? "∑ 数学影响" : "✦ AI 解读"}
      </span>
      <span className="pointer-events-none absolute right-0 top-full z-20 mt-2 w-56 rounded-lg border border-[var(--color-border)] bg-[#0d1114]/95 px-3 py-2 text-left text-[11px] leading-relaxed text-white opacity-0 shadow-[var(--shadow-panel)] transition-opacity group-hover:opacity-100 group-focus:opacity-100">
        {tooltip}
      </span>
    </span>
  );
}

export default function ScenarioSlider({ selectedEventIds, onChange, disabled = false }: ScenarioSliderProps) {
  const [events, setEvents] = useState<Event[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [draftIds, setDraftIds] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [impactModeFilter, setImpactModeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getEvents({ active_only: true, current_only: true }), api.getTeams()])
      .then(([eventData, teamData]) => {
        setEvents(eventData);
        setTeams(teamData);
      })
      .finally(() => setLoading(false));
  }, []);

  const teamById = useMemo(
    () => new Map(teams.map((team) => [team.id, team])),
    [teams],
  );
  const eventById = useMemo(
    () => new Map(events.map((event) => [event.id, event])),
    [events],
  );
  const activeEvents = useMemo(
    () => events.filter((event) => event.active && event.impact_mode !== "INVALID"),
    [events],
  );
  const draftSet = useMemo(() => new Set(draftIds), [draftIds]);

  const filteredEvents = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return activeEvents
      .filter((event) => {
        const team = teamById.get(event.team_id);
        const matchesSearch = !keyword || [event.title, event.description, team?.name_cn, team?.name]
          .some((value) => value?.toLowerCase().includes(keyword));
        return matchesSearch
          && (!teamFilter || event.team_id === Number(teamFilter))
          && (!typeFilter || event.type === typeFilter)
          && (!severityFilter || event.severity === severityFilter)
          && (!impactModeFilter || event.impact_mode === impactModeFilter);
      })
      .sort((a, b) => Number(draftSet.has(b.id)) - Number(draftSet.has(a.id)));
  }, [activeEvents, draftSet, impactModeFilter, search, severityFilter, teamById, teamFilter, typeFilter]);

  useEffect(() => setPage(1), [search, teamFilter, typeFilter, severityFilter, impactModeFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredEvents.length / PAGE_SIZE));
  const visibleEvents = filteredEvents.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const selectedEvents = selectedEventIds
    .map((id) => eventById.get(id))
    .filter((event): event is Event => Boolean(event));
  const selectedMathCount = selectedEvents.filter((event) => event.impact_mode === "MATH").length;
  const selectedNarrativeCount = selectedEvents.filter((event) => event.impact_mode === "NARRATIVE").length;

  const showDrawer = () => {
    setDraftIds(selectedEventIds);
    setApplyError(null);
    setOpen(true);
  };

  const toggleDraft = (eventId: number) => {
    setDraftIds((current) => current.includes(eventId)
      ? current.filter((id) => id !== eventId)
      : [...current, eventId]);
  };

  const applySelection = async (ids: number[], closeOnSuccess: boolean) => {
    setApplying(true);
    setApplyError(null);
    try {
      await onChange(ids);
      if (closeOnSuccess) setOpen(false);
    } catch (error) {
      setApplyError(error instanceof Error ? error.message : "事件情景模拟失败");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="mb-4">
      <div className="dashboard-glass flex flex-wrap items-center gap-2 rounded-lg px-3 py-2.5 shadow-[var(--shadow-sm)]">
        <span className="dashboard-label uppercase text-white">情景事件</span>
        <span className="text-xs text-[var(--color-text-muted)]">
          已选择 {selectedEventIds.length} 项 · {selectedMathCount} 项影响数学模型 · {selectedNarrativeCount} 项用于 AI 解读
        </span>
        <div className="flex flex-wrap gap-1.5 flex-1 min-w-0">
          {selectedEvents.slice(0, 3).map((event) => (
            <span
              key={event.id}
              title={event.impact_mode === "MATH" ? "影响数学胜率模型" : "仅作为 AI 解读背景，不影响数学胜率"}
              className={`max-w-48 truncate rounded-full border px-2.5 py-1 text-xs ${event.impact_mode === "MATH"
                ? "border-[var(--color-gold)] bg-[var(--color-gold)]/20 text-[var(--color-gold)] shadow-[0_0_10px_rgba(230,183,16,0.2)]"
                : "border-dashed border-[var(--color-border)] bg-transparent text-[var(--color-text-muted)]"
              }`}
            >
              {event.team_name ?? teamById.get(event.team_id)?.name_cn}：{event.title}
            </span>
          ))}
          {selectedEvents.length > 3 && (
            <span className="rounded-full bg-[var(--color-bg)] px-2.5 py-1 text-xs text-[var(--color-text-muted)]">
              另有 {selectedEvents.length - 3} 项
            </span>
          )}
        </div>
        {selectedEventIds.length > 0 && (
          <button
            onClick={() => void applySelection([], false)}
            disabled={disabled || applying}
            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-40"
          >
            清空
          </button>
        )}
        <button onClick={showDrawer} disabled={loading || disabled || applying} className="rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-xs font-semibold text-[#1c1d21] transition-colors hover:bg-[var(--color-primary-hover)] disabled:opacity-50">
          {loading ? "加载中…" : "选择事件"}
        </button>
      </div>

      {!open && applyError && (
        <p className="mt-2 text-xs text-[var(--color-accent)]">{applyError}</p>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
          <button aria-label="关闭事件选择" onClick={() => setOpen(false)} className="absolute inset-0 bg-[#0d1114]/80" />
          <aside className="relative flex h-full w-full max-w-[520px] flex-col border-l border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-panel)]">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
              <div>
                <h2 className="text-lg font-bold">选择赛事事件</h2>
                <p className="text-xs text-[var(--color-text-muted)]">已选择 {draftIds.length} 项，应用后重新模拟</p>
              </div>
              <button onClick={() => setOpen(false)} className="text-sm text-[var(--color-text-muted)]">关闭</button>
            </div>

            <div className="grid grid-cols-2 gap-2 border-b border-[var(--color-border)] p-4">
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索球队或事件" className="col-span-2 rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" />
              <select value={teamFilter} onChange={(event) => setTeamFilter(event.target.value)} className="rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm">
                <option value="">全部球队</option>
                {teams.map((team) => <option key={team.id} value={team.id}>{team.name_cn}</option>)}
              </select>
              <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm">
                <option value="">全部类型</option>
                <option value="INJURY">伤病</option>
                <option value="COACHING">教练变动</option>
                <option value="TACTICAL">战术调整</option>
                <option value="MORALE">士气</option>
                <option value="OTHER">其他</option>
              </select>
              <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} className="rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm">
                <option value="">全部严重程度</option>
                <option value="CRITICAL">严重</option>
                <option value="MAJOR">重要</option>
                <option value="MINOR">一般</option>
              </select>
              <select value={impactModeFilter} onChange={(event) => setImpactModeFilter(event.target.value)} className="rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm">
                <option value="">全部影响类型</option>
                <option value="MATH">影响数学模型</option>
                <option value="NARRATIVE">仅用于 AI 解读</option>
              </select>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {visibleEvents.length === 0 ? (
                <p className="py-12 text-center text-sm text-[var(--color-text-muted)]">没有符合条件的事件</p>
              ) : visibleEvents.map((event) => {
                const selected = draftSet.has(event.id);
                const team = teamById.get(event.team_id);
                return (
                  <button key={event.id} onClick={() => toggleDraft(event.id)} className={`mb-2 w-full rounded-lg border p-3 text-left ${selected
                    ? event.impact_mode === "MATH"
                      ? "border-[var(--color-gold)] bg-[var(--color-gold)]/10 shadow-[0_0_16px_rgba(230,183,16,0.12)]"
                      : "border-dashed border-[var(--color-text-muted)] bg-[var(--color-surface-raised)]"
                    : event.impact_mode === "MATH"
                      ? "border-[var(--color-gold)]/25 bg-[var(--color-bg)]"
                      : "border-dashed border-[var(--color-border)] bg-[var(--color-bg)]"
                  }`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{team?.name_cn ?? event.team_name} · {event.title}</p>
                        <p className="mt-1 line-clamp-2 text-xs text-[var(--color-text-muted)]">{event.description || "暂无详细描述"}</p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <ImpactModeBadge event={event} />
                        <span className="rounded-full px-2 py-0.5 text-xs text-[var(--color-text-muted)]">{SEVERITY_LABELS[event.severity] ?? event.severity}</span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="border-t border-[var(--color-border)] p-4">
              {applyError && (
                <p className="mb-3 text-sm text-[var(--color-accent)]">{applyError}</p>
              )}
              <div className="mb-3 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                <span>共 {filteredEvents.length} 项</span>
                <div className="flex items-center gap-2">
                  <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="disabled:opacity-30">上一页</button>
                  <span>{page} / {totalPages}</span>
                  <button disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)} className="disabled:opacity-30">下一页</button>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setOpen(false)} className="flex-1 rounded-md border border-[var(--color-border)] py-2 text-sm transition-colors hover:border-[var(--color-text-muted)]">取消</button>
                <button
                  disabled={applying || disabled}
                  onClick={() => void applySelection(draftIds, true)}
                  className="flex-1 rounded-md bg-[var(--color-primary)] py-2 text-sm font-semibold text-[#1c1d21] disabled:opacity-50"
                >
                  {applying ? "模拟中…" : "应用并重新模拟"}
                </button>
              </div>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

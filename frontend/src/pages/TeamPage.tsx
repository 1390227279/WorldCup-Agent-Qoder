import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import EventImpactBadge from "../components/EventImpactBadge";
import MetricCard from "../components/MetricCard";
import { api } from "../services/api";
import type { Event, Team } from "../types";
import { resolveImpactMode } from "../utils/eventImpact";

function severityLabel(severity: string): string {
  if (severity === "CRITICAL") return "严重";
  if (severity === "MAJOR") return "重要";
  return "一般";
}

function EventCard({ event }: { event: Event }) {
  const mode = resolveImpactMode(event);
  const attack = event.impact?.attack_lambda_delta ?? event.impact?.attack;
  const concede = event.impact?.concede_lambda_delta ?? event.impact?.defense;
  return (
    <article className={`dashboard-card border-l-2 p-4 ${mode === "MATH" ? "border-l-[var(--color-primary)]" : "border-l-[var(--color-border)] border-dashed"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <EventImpactBadge event={event} />
            <span className="dashboard-label">{severityLabel(event.severity)}</span>
          </div>
          <h3 className="mt-2 font-semibold">{event.title}</h3>
        </div>
      </div>
      {event.description && <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-muted)]">{event.description}</p>}
      {mode === "MATH" ? (
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <span className="rounded-md bg-[var(--color-bg)] px-3 py-2">进球期望 {attack == null ? "未设置" : `${attack >= 0 ? "+" : ""}${(attack * 100).toFixed(1)}%`}</span>
          <span className="rounded-md bg-[var(--color-bg)] px-3 py-2">失球期望 {concede == null ? "未设置" : `${concede >= 0 ? "+" : ""}${(concede * 100).toFixed(1)}%`}</span>
        </div>
      ) : (
        <p className="mt-3 border-t border-dashed border-[var(--color-border)] pt-2 text-xs text-[var(--color-text-muted)]">只进入相关比赛的 AI 解读上下文，不改变胜率或晋级概率。</p>
      )}
      {event.source && <p className="mt-3 text-xs text-[var(--color-text-muted)]">来源：{event.source}</p>}
    </article>
  );
}

export default function TeamPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["team", id],
    queryFn: () => api.getTeam(Number(id)),
    enabled: Boolean(id),
  });
  const team = data as (Team & { events?: Event[] }) | undefined;

  if (isLoading) return <div className="flex min-h-[70vh] items-center justify-center text-[var(--color-text-muted)]">正在加载球队档案…</div>;
  if (error || !team) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <div className="dashboard-card p-8">
          <p className="font-semibold text-[var(--color-error)]">球队档案加载失败</p>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">{error instanceof Error ? error.message : "球队不存在"}</p>
          <button type="button" onClick={() => void refetch()} className="mt-4 rounded-md border border-[var(--color-border)] px-4 py-2 text-sm hover:border-[var(--color-primary)]">重新加载</button>
        </div>
      </div>
    );
  }

  const events = team.events ?? [];
  const mathEvents = events.filter((event) => resolveImpactMode(event) === "MATH");
  const narrativeEvents = events.filter((event) => resolveImpactMode(event) === "NARRATIVE");

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
      <header className="mb-6 border-b border-[var(--color-border)] pb-5">
        <Link to="/" className="dashboard-label transition-colors hover:text-white">预测总览 / 球队档案</Link>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <span className="rounded-md border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 px-2 py-0.5 font-mono text-xs text-[var(--color-primary)]">{team.fifa_code}</span>
              <span className="dashboard-label">{team.confederation}</span>
            </div>
            <h1 className="dashboard-title">{team.name_cn}</h1>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">{team.name}</p>
          </div>
          <span className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs text-[var(--color-text-muted)]">{team.tournament?.qualification_status ?? "未关联赛事"}</span>
        </div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="FIFA 排名" value={team.fifa_ranking?.toString() ?? "—"} />
        <MetricCard label="ELO 评分" value={team.elo_rating?.toFixed(0) ?? "—"} accent />
        <MetricCard label="世界杯冠军" value={team.stats?.world_cup_titles?.toString() ?? "0"} note="历史夺冠次数" />
        <MetricCard label="参赛次数" value={team.stats?.appearances?.toString() ?? "—"} />
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="dashboard-card h-fit p-5">
          <p className="dashboard-label uppercase">当前赛事关系</p>
          <dl className="mt-3 divide-y divide-[var(--color-border-muted)] text-sm">
            <div className="flex justify-between gap-4 py-3"><dt className="text-[var(--color-text-muted)]">赛事</dt><dd className="text-right">{team.tournament?.name_cn ?? "未关联"}</dd></div>
            <div className="flex justify-between gap-4 py-3"><dt className="text-[var(--color-text-muted)]">小组</dt><dd>{team.tournament?.group_name ?? "待定"}</dd></div>
            <div className="flex justify-between gap-4 py-3"><dt className="text-[var(--color-text-muted)]">档位</dt><dd>{team.tournament?.pot ? `第 ${team.tournament.pot} 档` : "待定"}</dd></div>
            <div className="flex justify-between gap-4 py-3"><dt className="text-[var(--color-text-muted)]">数据状态</dt><dd>{team.tournament?.status ?? "未知"}</dd></div>
            <div className="flex justify-between gap-4 py-3"><dt className="text-[var(--color-text-muted)]">历史成绩</dt><dd className="text-right">{team.stats?.best_result || (team.stats?.world_cup_titles ? `${team.stats.world_cup_titles} 次夺冠` : "尚未夺冠")}</dd></div>
          </dl>
        </aside>

        <main className="min-w-0 space-y-5">
          <section>
            <div className="mb-3 flex items-center justify-between">
              <div><p className="dashboard-label uppercase">概率变量</p><h2 className="mt-1 font-semibold">数学影响事件</h2></div>
              <span className="font-mono text-xs text-[var(--color-primary)]">{mathEvents.length} 项</span>
            </div>
            {mathEvents.length > 0 ? <div className="grid gap-3 lg:grid-cols-2">{mathEvents.map((event) => <EventCard key={event.id} event={event} />)}</div> : <div className="dashboard-card border-dashed p-6 text-sm text-[var(--color-text-muted)]">当前没有修改进球期望的数学事件。</div>}
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <div><p className="dashboard-label uppercase">分析语境</p><h2 className="mt-1 font-semibold">AI 叙事背景</h2></div>
              <span className="font-mono text-xs text-[var(--color-text-muted)]">{narrativeEvents.length} 项</span>
            </div>
            {narrativeEvents.length > 0 ? <div className="grid gap-3 lg:grid-cols-2">{narrativeEvents.map((event) => <EventCard key={event.id} event={event} />)}</div> : <div className="dashboard-card border-dashed p-6 text-sm text-[var(--color-text-muted)]">当前没有可用于 AI 解读的叙事背景。</div>}
          </section>
        </main>
      </div>
    </div>
  );
}

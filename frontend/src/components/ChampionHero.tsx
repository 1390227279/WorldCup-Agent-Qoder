import { motion } from "framer-motion";
import type { SimulationProbabilityEntry, SimulationResult } from "../types";

interface Props {
  simulation: SimulationResult | undefined;
}

function teamName(entry: SimulationProbabilityEntry): string {
  return entry.team.name_cn || entry.team.name || entry.team.fifa_code;
}

function formatProbability(probability: number): string {
  if (!Number.isFinite(probability)) return "暂无";
  return `${(Math.min(Math.max(probability, 0), 1) * 100).toFixed(1)}%`;
}

function TrophyMark() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="h-9 w-9 fill-none stroke-current" strokeWidth="2">
      <path d="M16 7h16v7c0 8-3.6 14-8 14s-8-6-8-14zM19 28h10M24 28v8M17 41h14" />
      <path d="M16 11H9v3c0 6 3 10 9 10M32 11h7v3c0 6-3 10-9 10" />
    </svg>
  );
}

export default function ChampionHero({ simulation }: Props) {
  if (!simulation) {
    return (
      <div className="dashboard-card flex min-h-72 items-center justify-center p-8 text-center">
        <div>
          <div className="mx-auto mb-4 h-8 w-8 animate-pulse rounded-md border border-[var(--color-primary)] bg-[var(--color-primary)]/10" />
          <p className="font-semibold">正在建立基础实力基线</p>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">完成全部赛事模拟后展示概率第一球队</p>
        </div>
      </div>
    );
  }

  const leader = simulation.summary?.probability_leader;
  if (!leader?.team) {
    return <div className="dashboard-card p-8 text-center text-[var(--color-text-muted)]">暂无可用的基线概率数据</div>;
  }

  const top3 = [
    leader,
    ...(simulation.summary.top3 ?? []).filter((entry) => entry.team.id !== leader.team.id),
  ].slice(0, 3);

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="dashboard-card relative overflow-hidden border-[var(--color-primary)]/25"
    >
      <div className="absolute inset-y-0 left-0 w-1 bg-[var(--color-primary)]" />
      <div className="grid min-h-72 gap-6 p-6 md:grid-cols-[minmax(0,1fr)_240px] md:p-8">
        <div className="flex min-w-0 flex-col justify-between">
          <div>
            <div className="mb-6 flex items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-lg border border-[var(--color-primary)]/40 bg-[var(--color-primary)]/10 text-[var(--color-primary)] shadow-[var(--shadow-glow)]">
                <TrophyMark />
              </span>
              <div>
                <p className="dashboard-label uppercase">基础实力概率第一</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">不含伤病、士气和战术事件</p>
              </div>
            </div>
            <p className="truncate text-4xl font-semibold tracking-tight text-white md:text-5xl">{teamName(leader)}</p>
            <p className="mt-2 font-mono text-sm text-[var(--color-text-muted)]">{leader.team.fifa_code} · ELO {leader.team.elo_rating?.toFixed(0) ?? "—"}</p>
          </div>

          <div className="mt-8 flex flex-wrap items-end gap-x-4 gap-y-2">
            <span className="font-mono text-5xl font-semibold leading-none text-[var(--color-primary)] md:text-6xl">{formatProbability(leader.probability)}</span>
            <span className="pb-1 text-sm text-[var(--color-text-muted)]">模拟夺冠概率</span>
          </div>
        </div>

        <div className="border-t border-[var(--color-border)] pt-5 md:border-l md:border-t-0 md:pl-6 md:pt-0">
          <p className="dashboard-label mb-4 uppercase">前三名基线</p>
          <div className="space-y-3">
            {top3.map((entry, index) => (
              <div key={entry.team.id} className="grid grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-3 border-b border-[var(--color-border-muted)] pb-3 last:border-0">
                <span className={index === 0 ? "font-mono text-[var(--color-primary)]" : "font-mono text-[var(--color-text-muted)]"}>0{index + 1}</span>
                <div className="min-w-0">
                  <p className="truncate font-semibold">{teamName(entry)}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{entry.team.fifa_code}</p>
                </div>
                <span className={index === 0 ? "font-mono font-semibold text-[var(--color-primary)]" : "font-mono text-white"}>{formatProbability(entry.probability)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.section>
  );
}

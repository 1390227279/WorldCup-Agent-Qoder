import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import type { Team, SimulationResult } from "../types";

interface Props {
  simulation: SimulationResult | undefined;
}

interface ProbabilityRow {
  team: Team;
  probability: number;
}

function displayTeamName(team: Team): string {
  return team.name_cn || team.name || team.fifa_code;
}

export default function ProbabilityBar({ simulation }: Props) {
  const summary = simulation?.summary;
  if (!summary) {
    return <div className="py-14 text-center text-[var(--color-text-muted)]">正在完成蒙特卡洛模拟...</div>;
  }

  const knownTeams = new Map<number, Team>();
  for (const advancement of Object.values(summary.advancement_probs ?? {})) {
    if (advancement?.team) knownTeams.set(advancement.team.id, advancement.team);
  }
  for (const entry of summary.top3 ?? []) {
    if (entry?.team) knownTeams.set(entry.team.id, entry.team);
  }
  if (summary.probability_leader?.team) knownTeams.set(summary.probability_leader.team.id, summary.probability_leader.team);

  const rows: ProbabilityRow[] = Object.entries(summary.champion_probs_by_team_id ?? {})
    .map(([teamId, probability]) => ({ team: knownTeams.get(Number(teamId)), probability }))
    .filter((row): row is ProbabilityRow => row.team != null && Number.isFinite(row.probability))
    .sort((a, b) => b.probability - a.probability || a.team.id - b.team.id);
  const leader = summary.probability_leader;
  const sorted = leader?.team
    ? [{ team: leader.team, probability: leader.probability }, ...rows.filter((row) => row.team.id !== leader.team.id)].slice(0, 10)
    : rows.slice(0, 10);
  const maxProbability = Math.max(...sorted.map((row) => row.probability), 0.01);

  if (sorted.length === 0) return <div className="py-14 text-center text-[var(--color-text-muted)]">暂无可用的夺冠概率数据</div>;

  return (
    <div className="divide-y divide-[var(--color-border-muted)]">
      {sorted.map(({ team, probability }, index) => {
        const pct = Math.min(Math.max(probability, 0), 1) * 100;
        const relativeWidth = Math.max((probability / maxProbability) * 100, 2);
        return (
          <Link key={team.id} to={`/team/${team.id}`} className="group grid grid-cols-[28px_minmax(80px,130px)_minmax(100px,1fr)_58px] items-center gap-3 py-3 transition-colors hover:bg-[var(--color-surface-raised)]/70 sm:grid-cols-[32px_150px_minmax(120px,1fr)_68px]">
            <span className={index === 0 ? "font-mono text-sm text-[var(--color-primary)]" : "font-mono text-sm text-[var(--color-text-muted)]"}>{String(index + 1).padStart(2, "0")}</span>
            <div className="min-w-0">
              <p className={index === 0 ? "truncate font-semibold text-[var(--color-primary)]" : "truncate font-medium text-white"}>{displayTeamName(team)}</p>
              <p className="text-[11px] text-[var(--color-text-muted)]">{team.fifa_code}</p>
            </div>
            <div className="h-2 overflow-hidden rounded-sm bg-[var(--color-border-muted)]">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${relativeWidth}%` }}
                transition={{ delay: index * 0.03, duration: 0.45 }}
                className={index === 0 ? "h-full bg-[var(--color-primary)] shadow-[var(--shadow-glow)]" : index < 3 ? "h-full bg-[var(--color-secondary)]" : "h-full bg-[var(--color-border)] group-hover:bg-[var(--color-text-muted)]"}
              />
            </div>
            <span className={index === 0 ? "text-right font-mono font-semibold text-[var(--color-primary)]" : "text-right font-mono text-white"}>{pct.toFixed(1)}%</span>
          </Link>
        );
      })}
    </div>
  );
}

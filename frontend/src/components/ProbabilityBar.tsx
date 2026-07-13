import { motion } from "framer-motion";
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
    return (
      <div className="bg-[var(--color-surface)] rounded-xl p-8 text-center">
        <p className="text-[var(--color-text-muted)]">
          正在完成蒙特卡洛模拟...
        </p>
      </div>
    );
  }

  const knownTeams = new Map<number, Team>();
  for (const advancement of Object.values(summary.advancement_probs ?? {})) {
    if (advancement?.team) knownTeams.set(advancement.team.id, advancement.team);
  }
  for (const entry of summary.top3 ?? []) {
    if (entry?.team) knownTeams.set(entry.team.id, entry.team);
  }
  if (summary.probability_leader?.team) {
    knownTeams.set(summary.probability_leader.team.id, summary.probability_leader.team);
  }

  const rows: ProbabilityRow[] = Object.entries(
    summary.champion_probs_by_team_id ?? {},
  )
    .map(([teamId, probability]) => ({
      team: knownTeams.get(Number(teamId)),
      probability,
    }))
    .filter((row): row is ProbabilityRow => (
      row.team != null && Number.isFinite(row.probability)
    ))
    .sort((a, b) => b.probability - a.probability || a.team.id - b.team.id);

  const leader = summary.probability_leader;
  const leaderRow = leader?.team && Number.isFinite(leader.probability)
    ? { team: leader.team, probability: leader.probability }
    : undefined;
  const sorted = leaderRow
    ? [leaderRow, ...rows.filter((row) => row.team.id !== leaderRow.team.id)].slice(0, 10)
    : rows.slice(0, 10);

  if (sorted.length === 0) {
    return (
      <div className="bg-[var(--color-surface)] rounded-xl p-8 text-center">
        <p className="text-[var(--color-text-muted)]">暂无可用的夺冠概率数据</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {sorted.map(({ team, probability }, i) => {
        const displayName = displayTeamName(team);
        const normalizedProbability = Math.min(Math.max(probability, 0), 1);
        const pct = (normalizedProbability * 100).toFixed(1);

        return (
          <motion.div
            key={team.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className="flex items-center gap-4"
          >
            <span className="w-8 text-right text-sm text-[var(--color-text-muted)]">
              {i + 1}
            </span>
            <span className="w-20 text-sm font-medium text-right">
              {displayName}
            </span>
            <div className="flex-1 bg-[var(--color-bg)] rounded-full h-6 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(Number(pct), 1)}%` }}
                transition={{ delay: i * 0.05 + 0.3, duration: 0.6 }}
                className="h-full rounded-full"
                style={{
                  background:
                    i === 0
                      ? "linear-gradient(90deg, #f5c518, #e94560)"
                      : i < 3
                        ? "linear-gradient(90deg, #1a56db, #6366f1)"
                        : "linear-gradient(90deg, #374151, #4b5563)",
                }}
              />
            </div>
            <span className="w-16 text-sm font-mono text-right">{pct}%</span>
          </motion.div>
        );
      })}
    </div>
  );
}

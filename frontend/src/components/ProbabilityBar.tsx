import { motion } from "framer-motion";
import type { Team, SimulationResult } from "../types";

interface Props {
  simulation: SimulationResult | undefined;
  teams: Team[] | undefined;
}

export default function ProbabilityBar({ simulation, teams }: Props) {
  if (!simulation?.champion_probs || !teams) {
    return (
      <div className="bg-[var(--color-surface)] rounded-xl p-8 text-center">
        <p className="text-[var(--color-text-muted)]">
          等待 Agent 完成蒙特卡洛模拟...
        </p>
      </div>
    );
  }

  const sorted = Object.entries(simulation.champion_probs)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);

  return (
    <div className="space-y-3">
      {sorted.map(([name, prob], i) => {
        const team = teams.find(
          (t) => t.name === name || t.name_cn === name
        );
        const displayName = team?.name_cn ?? name;
        const pct = (prob * 100).toFixed(1);

        return (
          <motion.div
            key={name}
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

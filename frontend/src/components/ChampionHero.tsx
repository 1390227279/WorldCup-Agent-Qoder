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

export default function ChampionHero({ simulation }: Props) {
  if (!simulation) {
    return (
      <div className="bg-[var(--color-surface)] rounded-2xl p-12 text-center">
        <p className="text-4xl mb-4">⚽</p>
        <p className="text-xl text-[var(--color-text-muted)]">
          正在计算基础实力基线...
        </p>
        <p className="text-sm text-[var(--color-text-muted)] mt-2">
          完成全部赛事模拟后，此区域将展示夺冠概率最高的球队
        </p>
      </div>
    );
  }

  const leader = simulation.summary?.probability_leader;
  if (!leader?.team) {
    return (
      <div className="bg-[var(--color-surface)] rounded-2xl p-12 text-center">
        <p className="text-xl text-[var(--color-text-muted)]">
          暂无可用的基线概率数据
        </p>
      </div>
    );
  }

  const top3 = [
    leader,
    ...(simulation.summary.top3 ?? []).filter(
      (entry) => entry.team.id !== leader.team.id,
    ),
  ].slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="bg-[var(--color-surface)] rounded-2xl p-8 md:p-12 text-center relative overflow-hidden"
    >
      {/* Gold glow background */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          background:
            "radial-gradient(circle at center, var(--color-gold) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10">
        <p className="text-sm text-[var(--color-text-muted)] uppercase tracking-widest mb-4">
          基础实力基线（不含事件） · 蒙特卡洛 {simulation.model.iterations.toLocaleString()} 次完整赛事模拟
        </p>

        <motion.div
          initial={{ scale: 0.8 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.3, type: "spring", stiffness: 200 }}
        >
          <p className="text-6xl mb-3">🏆</p>
          <h2 className="text-5xl font-bold text-[var(--color-gold)] mb-2">
            {teamName(leader)}
          </h2>
          <div className="inline-flex items-center gap-2 bg-[var(--color-gold)]/10 rounded-full px-6 py-2">
            <span className="text-3xl font-bold text-[var(--color-gold)]">
              {formatProbability(leader.probability)}
            </span>
            <span className="text-sm text-[var(--color-text-muted)]">
              夺冠概率
            </span>
          </div>
        </motion.div>

        {/* Top 3 summary */}
        <div className="mt-8 flex justify-center gap-8 flex-wrap">
          {top3.map((entry, i) => {
            const colors = [
              "text-[var(--color-gold)]",
              "text-[var(--color-silver)]",
              "text-[var(--color-bronze)]",
            ];
            return (
              <div key={entry.team.id} className="text-center">
                <p className={`text-2xl font-bold ${colors[i]}`}>
                  {formatProbability(entry.probability)}
                </p>
                <p className="text-sm text-[var(--color-text-muted)]">
                  {teamName(entry)}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
